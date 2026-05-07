"""Data models used throughout the application."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class StatusEntry:
    """Represents a single file's status from ``git status --porcelain``."""

    raw_line: str
    index_status: str
    worktree_status: str
    path: str
    display_path: str
    is_untracked: bool
    has_staged: bool
    has_unstaged: bool
    old_path: Optional[str] = None


@dataclass
class GitInfo:
    """Staged-change information used for commit message generation."""

    branch_name: str
    repo_name: str
    repo_path: str
    staged_files: List[str]
    git_diff: str
    date: str
    files_changed: str


@dataclass
class ReviewInfo:
    """All-change information used for AI code review."""

    branch_name: str
    repo_name: str
    repo_path: str
    status_entries: List[StatusEntry]
    git_diff: str
    date: str
    files_changed: str
    additional_context: str = ""
