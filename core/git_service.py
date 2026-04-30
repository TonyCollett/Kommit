"""Git repository operations via subprocess."""

import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from core.models import GitInfo, ReviewInfo, StatusEntry


class GitService:
    """Encapsulates all git CLI interactions for a single repository."""

    STAGED_STATES = {"M", "A", "D", "R", "C", "T", "U"}
    WORKTREE_STATES = {"M", "A", "D", "R", "C", "T", "U"}

    def __init__(self, repo_path: Optional[str] = None):
        self.repo_path = repo_path

    def set_repo_path(self, path: str):
        self.repo_path = path

    # ── Low-level helpers ────────────────────────────────────────────

    def run(self, args: list, check: bool = True) -> subprocess.CompletedProcess:
        """Run a git command in the current repository."""
        return subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            check=check,
        )

    @staticmethod
    def is_valid_repo(path: str) -> bool:
        """Return whether *path* contains a valid git repository."""
        try:
            if not os.path.exists(path):
                return False
            result = subprocess.run(
                ["git", "status"], cwd=path, capture_output=True, text=True
            )
            return result.returncode == 0
        except Exception:
            return False

    @staticmethod
    def get_error_message(error: subprocess.CalledProcessError) -> str:
        """Extract a readable error message from a failed git command."""
        for value in (error.stderr, error.stdout, str(error)):
            if value and value.strip():
                return value.strip()
        return "Git command failed."

    # ── Repository information ───────────────────────────────────────

    def get_current_branch(self) -> str:
        result = self.run(["branch", "--show-current"])
        name = result.stdout.strip()
        if not name:
            raise Exception("Unable to determine the current branch name.")
        return name

    def get_repo_name(self) -> str:
        result = self.run(["remote", "get-url", "origin"], check=False)
        url = result.stdout.strip() if result.returncode == 0 else ""
        if url:
            return Path(url).stem.replace(".git", "")
        return Path(self.repo_path).name

    def get_local_branches(self) -> List[str]:
        result = self.run(["branch", "--format=%(refname:short)"])
        return [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]

    def get_remote_branches(self) -> List[str]:
        result = self.run(["branch", "-r", "--format=%(refname:short)"])
        branches = [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]
        return [b for b in branches if "/HEAD" not in b]

    def get_remote_url(self, remote_name: str = "origin") -> str:
        """Return the remote URL for *remote_name*, or empty string if none."""
        result = self.run(["remote", "get-url", remote_name], check=False)
        return result.stdout.strip() if result.returncode == 0 else ""

    def has_remote(self, remote_name: str = "origin") -> bool:
        result = self.run(["remote", "get-url", remote_name], check=False)
        return result.returncode == 0

    def has_upstream_branch(self) -> bool:
        result = self.run(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}"],
            check=False,
        )
        return result.returncode == 0

    # ── Status and diffs ─────────────────────────────────────────────

    def get_status_entries(self) -> List[StatusEntry]:
        """Parse ``git status --porcelain`` output into :class:`StatusEntry` objects."""
        status_result = self.run(["status", "--porcelain"])
        entries: List[StatusEntry] = []

        for raw_line in status_result.stdout.splitlines():
            if not raw_line:
                continue

            index_status = raw_line[0]
            worktree_status = raw_line[1]
            raw_path = raw_line[3:]
            old_path = None
            path = raw_path

            if " -> " in raw_path and (
                index_status in {"R", "C"} or worktree_status in {"R", "C"}
            ):
                old_path, path = raw_path.split(" -> ", 1)

            is_untracked = raw_line.startswith("??")
            entries.append(
                StatusEntry(
                    raw_line=raw_line,
                    index_status=index_status,
                    worktree_status=worktree_status,
                    path=path,
                    old_path=old_path,
                    display_path=raw_path,
                    is_untracked=is_untracked,
                    has_staged=index_status in self.STAGED_STATES,
                    has_unstaged=is_untracked or worktree_status in self.WORKTREE_STATES,
                )
            )

        return entries

    def get_file_diff_sections(
        self, entry: StatusEntry, context_lines: int = 4
    ) -> List[Tuple[str, str]]:
        """Return ``(title, diff_text)`` sections for a single changed file."""
        sections: List[Tuple[str, str]] = []
        file_path = entry.path
        context_arg = f"--unified={context_lines}"

        if entry.has_staged:
            staged_diff = self.run(
                ["diff", "--cached", context_arg, "--", file_path]
            ).stdout
            if staged_diff.strip():
                sections.append(("Staged Changes", staged_diff))

        if entry.is_untracked:
            sections.append(("Untracked File", self._build_untracked_diff(file_path)))
        elif entry.has_unstaged:
            unstaged_diff = self.run(
                ["diff", context_arg, "--", file_path]
            ).stdout
            if unstaged_diff.strip():
                sections.append(("Unstaged Changes", unstaged_diff))

        return sections

    def _build_untracked_diff(self, relative_path: str, max_lines: int = 500) -> str:
        """Build a synthetic diff preview for an untracked file."""
        full_path = Path(self.repo_path) / relative_path
        diff_header = [
            f"diff --git a/{relative_path} b/{relative_path}",
            "new file mode 100644",
            "--- /dev/null",
            f"+++ b/{relative_path}",
        ]

        try:
            file_bytes = full_path.read_bytes()
        except Exception as e:
            return (
                "\n".join(diff_header + [f"[Unable to read file contents: {e}]"]) + "\n"
            )

        if b"\x00" in file_bytes:
            return "\n".join(diff_header + ["[Binary file preview unavailable]"]) + "\n"

        file_text = file_bytes.decode("utf-8", errors="replace")
        content_lines = file_text.splitlines()
        displayed_lines = content_lines[:max_lines]
        hunk_size = len(displayed_lines)
        diff_body = [f"@@ -0,0 +1,{hunk_size} @@"]
        diff_body.extend(f"+{line}" for line in displayed_lines)

        if len(content_lines) > max_lines:
            diff_body.append(
                f"+[... truncated {len(content_lines) - max_lines} more lines ...]"
            )

        if file_text.endswith("\n"):
            return "\n".join(diff_header + diff_body) + "\n"

        return (
            "\n".join(diff_header + diff_body + [r"\ No newline at end of file"]) + "\n"
        )

    # ── Staging operations ───────────────────────────────────────────

    def stage_file(self, relative_path: str):
        self.run(["add", "--", relative_path])

    def unstage_file(self, relative_path: str):
        try:
            self.run(["restore", "--staged", "--", relative_path])
        except subprocess.CalledProcessError:
            self.run(["reset", "HEAD", "--", relative_path])

    def discard_unstaged_changes(self, entry: StatusEntry):
        """Discard only unstaged changes, preserving staged content."""
        full_path = Path(self.repo_path) / entry.path

        if entry.is_untracked:
            if full_path.is_dir():
                shutil.rmtree(full_path)
            elif full_path.exists():
                full_path.unlink()
            return

        try:
            self.run(["restore", "--worktree", "--", entry.path])
        except subprocess.CalledProcessError:
            self.run(["checkout", "--", entry.path])

    # ── Commit / push / sync ─────────────────────────────────────────

    def commit(self, message: str):
        self.run(["commit", "-m", message])

    def push(self):
        if self.has_upstream_branch():
            self.run(["push"])
            return

        if not self.has_remote("origin"):
            raise Exception("Remote 'origin' is not configured for this repository.")

        branch = self.get_current_branch()
        self.run(["push", "--set-upstream", "origin", branch])

    def sync(self):
        if self.has_upstream_branch():
            self.run(["pull", "--rebase"])
        self.push()

    def checkout(self, branch_name: str):
        self.run(["checkout", branch_name])

    def checkout_remote(self, remote_branch: str, local_name: str):
        result = self.run(["checkout", local_name], check=False)
        if result.returncode != 0:
            self.run(["checkout", "-b", local_name, remote_branch])

    # ── Aggregated info for AI ───────────────────────────────────────

    def get_git_info(self) -> GitInfo:
        """Gather staged-change information for commit message generation."""
        branch_name = self.get_current_branch()
        repo_name = self.get_repo_name()

        staged_result = self.run(["diff", "--cached", "--name-only"])
        staged_files = (
            staged_result.stdout.strip().split("\n")
            if staged_result.stdout.strip()
            else []
        )

        diff_result = self.run(["diff", "--cached"])
        git_diff = diff_result.stdout

        return GitInfo(
            branch_name=branch_name,
            repo_name=repo_name,
            repo_path=self.repo_path,
            staged_files=staged_files,
            git_diff=git_diff,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            files_changed=", ".join(staged_files),
        )

    def get_review_info(self) -> ReviewInfo:
        """Gather all-change information for code review."""
        branch_name = self.get_current_branch()
        repo_name = self.get_repo_name()
        status_entries = self.get_status_entries()

        change_descriptions = []
        diff_sections = []

        for entry in status_entries:
            states = []
            if entry.has_staged:
                states.append("staged")
            if entry.has_unstaged:
                states.append("unstaged")
            if entry.is_untracked:
                states.append("untracked")

            state_text = ", ".join(states) if states else "changed"
            change_descriptions.append(f"{entry.display_path} ({state_text})")

            for section_title, diff_text in self.get_file_diff_sections(entry):
                diff_sections.append(f"File: {entry.display_path}")
                diff_sections.append(f"[{section_title}]")
                diff_sections.append(diff_text.rstrip())
                diff_sections.append("")

        return ReviewInfo(
            branch_name=branch_name,
            repo_name=repo_name,
            repo_path=self.repo_path,
            status_entries=status_entries,
            git_diff="\n".join(diff_sections).strip(),
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            files_changed=", ".join(change_descriptions),
        )
