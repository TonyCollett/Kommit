"""Repository management dialog."""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from core.config_manager import ConfigManager
from core.git_service import GitService


class RepositoryManager(QDialog):
    """Modal dialog for adding, removing, and validating git repositories."""

    def __init__(self, parent, config: ConfigManager, git: GitService):
        super().__init__(parent)
        self.config = config
        self.git = git

        self.setWindowTitle("Repository Manager")
        self.resize(600, 400)
        self.setMinimumSize(500, 300)

        self._setup_ui()
        self._refresh_list()

    # ── UI construction ──────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        header = QLabel("Manage Git Repositories")
        header.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(header)

        self.repo_list = QListWidget()
        layout.addWidget(self.repo_list, stretch=1)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("Add Repository")
        add_btn.clicked.connect(self._add_repo)
        btn_row.addWidget(add_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_repo)
        btn_row.addWidget(remove_btn)

        validate_btn = QPushButton("Validate All")
        validate_btn.clicked.connect(self._validate_all)
        btn_row.addWidget(validate_btn)

        detect_btn = QPushButton("Auto-Detect")
        detect_btn.clicked.connect(self._auto_detect)
        btn_row.addWidget(detect_btn)

        btn_row.addStretch()

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)

        layout.addLayout(btn_row)

    # ── List ─────────────────────────────────────────────────────────

    def _refresh_list(self):
        self.repo_list.clear()
        for path in self.config.get_repository_paths():
            marker = "\u2713" if GitService.is_valid_repo(path) else "\u2717"
            self.repo_list.addItem(f"{marker}  {Path(path).name}  —  {path}")

    # ── Actions ──────────────────────────────────────────────────────

    def _add_repo(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select Git Repository Folder"
        )
        if not folder:
            return

        if not GitService.is_valid_repo(folder):
            QMessageBox.critical(
                self,
                "Error",
                "Selected folder is not a valid git repository.",
            )
            return

        paths = self.config.get_repository_paths()
        if folder in paths:
            QMessageBox.warning(
                self, "Warning", "Repository already exists in the list."
            )
            return

        paths.append(folder)
        self.config.save_repository_paths(paths)
        self._refresh_list()
        QMessageBox.information(self, "Success", "Repository added successfully!")

    def _remove_repo(self):
        row = self.repo_list.currentRow()
        if row < 0:
            QMessageBox.warning(
                self, "Warning", "Please select a repository to remove."
            )
            return

        paths = self.config.get_repository_paths()
        if row < len(paths):
            removed = paths.pop(row)
            self.config.save_repository_paths(paths)
            self._refresh_list()
            QMessageBox.information(
                self, "Success", f"Repository removed: {removed}"
            )

    def _validate_all(self):
        paths = self.config.get_repository_paths()
        valid = [p for p in paths if GitService.is_valid_repo(p)]

        if len(valid) != len(paths):
            removed = len(paths) - len(valid)
            self.config.save_repository_paths(valid)
            self._refresh_list()
            QMessageBox.information(
                self,
                "Validation Complete",
                f"Removed {removed} invalid repository/ies.",
            )
        else:
            QMessageBox.information(
                self, "Validation Complete", "All repositories are valid."
            )

    def _auto_detect(self):
        common_paths = [
            Path.home() / name
            for name in ("Documents", "Projects", "Development", "dev", "src", "git")
        ]
        common_paths.append(Path.home())

        found = []
        for base in common_paths:
            if not base.exists():
                continue
            for child in base.iterdir():
                if child.is_dir() and GitService.is_valid_repo(str(child)):
                    found.append(str(child))

        existing = self.config.get_repository_paths()
        new = [r for r in found if r not in existing]

        if new:
            all_paths = existing + new
            self.config.save_repository_paths(all_paths)
            self._refresh_list()
            QMessageBox.information(
                self,
                "Auto-Detection Complete",
                f"Found and added {len(new)} new repositories.",
            )
        else:
            QMessageBox.information(
                self,
                "Auto-Detection Complete",
                "No new repositories found.",
            )
