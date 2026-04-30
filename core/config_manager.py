"""Configuration management using INI files."""

import configparser
import json
from pathlib import Path
from typing import List, Optional


class ConfigManager:
    """Manages application configuration stored in an INI file."""

    DEFAULT_CONFIG = {
        "API": {
            "provider": "openai",
            "openai_api_key": "",
            "anthropic_api_key": "",
            "gemini_api_key": "",
            "ollama_host": "http://localhost:11434",
            "model": "gpt-4.1-mini",
        },
        "REPOSITORIES": {
            "paths": "",
            "current_repo": "",
        },
        "PROMPT": {
            "system_prompt": (
                "You are a helpful assistant that generates concise, clear git commit messages.\n"
                "Follow conventional commit format when appropriate (feat:, fix:, docs:, etc.).\n"
                "Be specific about what changed and why."
            ),
            "user_prompt": (
                "Based on the following git diff and context, generate a commit message:\n\n"
                "Repository: {{repo_name}}\n"
                "Branch: {{branch_name}}\n"
                "Date: {{date}}\n"
                "Files changed: {{files_changed}}\n\n"
                "Git diff:\n{{git_diff}}\n\n"
                "Generate a commit message that is:\n"
                "1. Clear and concise\n"
                "2. Explains what changed and why\n"
                "3. Uses conventional commit format if appropriate\n"
                "4. Is under 72 characters for the first line"
            ),
        },
        "CODE_REVIEW": {
            "system_prompt": (
                "You are a senior software engineer performing a focused code review on git changes.\n"
                "Look for correctness issues, regressions, edge cases, security problems, "
                "performance risks, and maintainability concerns.\n"
                "Only report findings that are supported by the provided changes and be specific "
                "about the impact.\n"
                "If no significant issues are present, say so clearly."
            ),
        },
        "ROOT_CAUSE": {
            "system_prompt": "Generate a root cause summary from this code",
        },
        "GUI": {
            "always_on_top": "true",
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).resolve().parent.parent / "git_commit_ai_config.ini"
        self.config_file = config_path
        self.config = configparser.ConfigParser(interpolation=None)
        self.load_config()

    def load_config(self):
        """Load configuration from file, creating defaults for missing values."""
        if self.config_file.exists():
            self.config.read(self.config_file)

        for section, options in self.DEFAULT_CONFIG.items():
            if not self.config.has_section(section):
                self.config.add_section(section)
            for key, value in options.items():
                if not self.config.has_option(section, key):
                    self.config.set(section, key, value)

        self.save_config()

    def save_config(self):
        """Persist current configuration to disk."""
        with open(self.config_file, "w") as f:
            self.config.write(f)

    # ── Generic accessors ────────────────────────────────────────────

    def get(self, section: str, key: str, fallback: Optional[str] = None) -> str:
        return self.config.get(section, key, fallback=fallback)

    def set(self, section: str, key: str, value: str):
        self.config.set(section, key, value)

    def getboolean(self, section: str, key: str, fallback: bool = False) -> bool:
        return self.config.getboolean(section, key, fallback=fallback)

    # ── Repository helpers ───────────────────────────────────────────

    def get_repository_paths(self) -> List[str]:
        paths_json = self.get("REPOSITORIES", "paths", fallback="[]")
        try:
            return json.loads(paths_json) if paths_json else []
        except json.JSONDecodeError:
            return []

    def save_repository_paths(self, paths: List[str]):
        self.set("REPOSITORIES", "paths", json.dumps(paths))
        self.save_config()

    @property
    def current_repo(self) -> str:
        return self.get("REPOSITORIES", "current_repo", fallback="")

    @current_repo.setter
    def current_repo(self, value: str):
        self.set("REPOSITORIES", "current_repo", value)
        self.save_config()

    # ── Convenience properties ───────────────────────────────────────

    @property
    def provider(self) -> str:
        return self.get("API", "provider")

    @property
    def model(self) -> str:
        return self.get("API", "model")

    @property
    def always_on_top(self) -> bool:
        return self.getboolean("GUI", "always_on_top")
