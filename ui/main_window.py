"""Main application window."""

import os
import platform
import re
import subprocess
from pathlib import Path

from PySide6.QtCore import QEvent, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
    QProgressDialog,
)

from core.ai_service import AIService
from core.config_manager import ConfigManager
from core.git_service import GitService
from ui.widgets.text_dialog import TextDialog
from ui.widgets.worker import WorkerThread


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self, config: ConfigManager):
        super().__init__()
        self.config = config
        self.git = GitService()
        self.ai = AIService(config)

        self.current_repo_path = None
        self.changes_dialog = None
        self._app_had_focus = True
        self._active_thread = None

        self._setup_ui()
        self._check_packages()
        self.refresh_repositories()

    # ── UI construction ──────────────────────────────────────────────

    def _setup_ui(self):
        self.setWindowTitle("Kommit - AI Powered Git Generator")
        self.resize(1000, 520)
        self.setMinimumSize(820, 420)

        if self.config.always_on_top:
            self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)

        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)

        # ── Left panel ──
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)

        # Repository selection
        repo_grp = QGroupBox("Repository Selection")
        repo_lay = QHBoxLayout(repo_grp)
        repo_lay.addWidget(QLabel("Repository:"))
        self.repo_combo = QComboBox()
        self.repo_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.repo_combo.setMinimumContentsLength(30)
        self.repo_combo.currentIndexChanged.connect(self._on_repo_selected)
        repo_lay.addWidget(self.repo_combo, stretch=1)
        manage_btn = QPushButton("Manage Repos")
        manage_btn.clicked.connect(self._manage_repositories)
        repo_lay.addWidget(manage_btn)
        left_lay.addWidget(repo_grp)

        # Repo info row
        info_row = QHBoxLayout()
        self.repo_info_label = QLabel("No repository selected")
        self.repo_info_label.setStyleSheet("color: gray;")
        info_row.addWidget(self.repo_info_label)

        self.changes_btn = QPushButton("Changes")
        self.changes_btn.setEnabled(False)
        self.changes_btn.clicked.connect(self._open_changes)
        info_row.addWidget(self.changes_btn)

        self.refresh_btn = QPushButton("\u27F3")  # ⟳
        self.refresh_btn.setFixedWidth(30)
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self._refresh_status)
        info_row.addWidget(self.refresh_btn)

        info_row.addStretch()
        left_lay.addLayout(info_row)

        # Buttons row
        btn_row = QHBoxLayout()

        # Generate-actions drop-down
        generate_btn = QPushButton("Generate Actions")
        generate_menu = QMenu(self)
        generate_menu.addAction(
            "Generate Commit Message", self._generate_clicked
        )
        generate_menu.addAction(
            "AI Code Review", self._review_clicked
        )
        generate_menu.addAction(
            "Root Cause Summary", self._root_cause_clicked
        )
        generate_btn.setMenu(generate_menu)
        btn_row.addWidget(generate_btn)

        config_btn = QPushButton("Configure")
        config_btn.clicked.connect(self._configure_clicked)
        btn_row.addWidget(config_btn)

        # Commit-actions drop-down
        self.commit_btn = QPushButton("Commit Actions")
        self.commit_btn.setEnabled(False)
        commit_menu = QMenu(self)
        commit_menu.addAction("Copy to Clipboard", self._copy_message)
        commit_menu.addSeparator()
        commit_menu.addAction(
            "Commit Staged Files", lambda: self._run_commit("commit")
        )
        commit_menu.addAction("Commit and Push", lambda: self._run_commit("push"))
        commit_menu.addAction("Commit and Sync", lambda: self._run_commit("sync"))
        self.commit_btn.setMenu(commit_menu)
        btn_row.addWidget(self.commit_btn)

        # Repo-actions drop-down
        repo_act_btn = QPushButton("Repository Actions")
        repo_menu = QMenu(self)
        repo_menu.addAction("Open in Terminal", self._open_terminal)
        repo_menu.addAction("Open in Explorer", self._open_explorer)
        repo_menu.addAction("Raise Pull Request", self._raise_pull_request)
        repo_act_btn.setMenu(repo_menu)
        btn_row.addWidget(repo_act_btn)

        btn_row.addStretch()
        left_lay.addLayout(btn_row)

        # Text area
        self.text_area = QTextEdit()
        self.text_area.setPlaceholderText(
            "Generated commit message will appear here..."
        )
        left_lay.addWidget(self.text_area, stretch=1)

        root.addWidget(left, stretch=3)

        # ── Right panel (branches) ──
        branch_grp = QGroupBox("Branches")
        branch_lay = QVBoxLayout(branch_grp)

        self.branch_tree = QTreeWidget()
        self.branch_tree.setHeaderHidden(True)
        self.branch_tree.setColumnCount(1)
        self.branch_tree.setIndentation(14)
        self.branch_tree.itemDoubleClicked.connect(self._on_branch_double_click)
        branch_lay.addWidget(self.branch_tree, stretch=1)

        hint = QLabel("Double-click to switch")
        hint.setStyleSheet("color: gray;")
        branch_lay.addWidget(hint)

        branch_grp.setFixedWidth(230)
        root.addWidget(branch_grp)

        # Status bar
        self.statusBar().showMessage("Ready")

    # ── Focus handling ───────────────────────────────────────────────

    def changeEvent(self, event):
        if event.type() == QEvent.Type.ActivationChange:
            if self.isActiveWindow():
                if not self._app_had_focus:
                    self._app_had_focus = True
                    self._on_focus_regained()
            else:
                self._app_had_focus = False
        super().changeEvent(event)

    def _on_focus_regained(self):
        if self.current_repo_path:
            self._update_repo_info()
            self._refresh_branch_list()
            if self.changes_dialog and self.changes_dialog.isVisible():
                self.changes_dialog.refresh_contents()

    # ── Repository management ────────────────────────────────────────

    def refresh_repositories(self):
        """Reload the repo combo from config, validate, and select."""
        paths = self.config.get_repository_paths()
        valid = [p for p in paths if GitService.is_valid_repo(p)]

        self.repo_combo.blockSignals(True)
        self.repo_combo.clear()
        for p in valid:
            self.repo_combo.addItem(f"{Path(p).name}  ({p})", userData=p)
        self.repo_combo.blockSignals(False)

        current = self.config.current_repo
        if current and current in valid:
            self.repo_combo.setCurrentIndex(valid.index(current))
            self._select_repo(current)
        elif valid:
            self.repo_combo.setCurrentIndex(0)
            self._select_repo(valid[0])
        else:
            self.current_repo_path = None
            self._update_repo_info()

        self._update_api_status()
        self._refresh_branch_list()

    def _on_repo_selected(self, index: int):
        if index >= 0:
            path = self.repo_combo.itemData(index)
            if path:
                self._select_repo(path)

    def _select_repo(self, path: str):
        self.current_repo_path = path
        self.git.set_repo_path(path)
        self.config.current_repo = path
        self._update_repo_info()
        self._refresh_branch_list()
        if self.changes_dialog and self.changes_dialog.isVisible():
            self.changes_dialog.refresh_contents()
        self._reset_commit_state()

    def _update_repo_info(self):
        if not self.current_repo_path:
            self.repo_info_label.setText("No repository selected")
            self.repo_info_label.setStyleSheet("color: gray;")
            self.changes_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            return

        if not os.path.exists(self.current_repo_path):
            self.repo_info_label.setText("Repository not found")
            self.repo_info_label.setStyleSheet("color: red;")
            self.changes_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            return

        try:
            branch = self.git.get_current_branch()
            entries = self.git.get_status_entries()
            staged = sum(1 for e in entries if e.has_staged)
            unstaged = sum(1 for e in entries if e.has_unstaged)
            self.repo_info_label.setText(
                f"Branch: {branch} | Staged: {staged} | Unstaged: {unstaged}"
            )
            self.repo_info_label.setStyleSheet("")
            self.changes_btn.setEnabled(True)
            self.refresh_btn.setEnabled(True)
        except Exception:
            self.repo_info_label.setText("Error reading repository")
            self.repo_info_label.setStyleSheet("color: red;")
            self.changes_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)

    def _update_api_status(self):
        warning = self.ai.get_provider_status()
        if warning:
            self.statusBar().showMessage(warning)
        else:
            self.statusBar().showMessage("Ready")

    def _reset_commit_state(self):
        self.commit_btn.setEnabled(False)

    # ── Branch panel ─────────────────────────────────────────────────

    def _refresh_branch_list(self):
        self.branch_tree.clear()
        if not self.current_repo_path:
            return

        try:
            current = self.git.get_current_branch()
        except Exception:
            current = ""

        try:
            local = self.git.get_local_branches()
        except Exception:
            local = []

        try:
            remote = self.git.get_remote_branches()
        except Exception:
            remote = []

        bold = QFont()
        bold.setBold(True)

        local_node = QTreeWidgetItem(self.branch_tree, ["Local Branches"])
        local_node.setFont(0, bold)
        local_node.setExpanded(True)
        self._insert_branches(local_node, local, current)

        remote_node = QTreeWidgetItem(self.branch_tree, ["Remote Branches"])
        remote_node.setFont(0, bold)
        remote_node.setExpanded(True)
        self._insert_branches(remote_node, remote, "", expand=False)

    def _insert_branches(self, parent, branches, current_branch, expand=True):
        folder_map = {}
        for branch in sorted(branches):
            parts = branch.split("/")
            cur_parent = parent

            for part in parts[:-1]:
                key = (id(cur_parent), part)
                if key not in folder_map:
                    item = QTreeWidgetItem(cur_parent, [part])
                    item.setExpanded(expand)
                    folder_map[key] = item
                cur_parent = folder_map[key]

            leaf = QTreeWidgetItem(cur_parent, [parts[-1]])
            leaf.setData(0, Qt.ItemDataRole.UserRole, branch)

            if branch == current_branch:
                f = leaf.font(0)
                f.setBold(True)
                leaf.setFont(0, f)

    def _on_branch_double_click(self, item, _column):
        if item.childCount() > 0:
            return
        full_branch = item.data(0, Qt.ItemDataRole.UserRole)
        if not full_branch:
            return

        root = item
        while root.parent():
            root = root.parent()
        section = root.text(0)

        try:
            current = self.git.get_current_branch()
        except Exception:
            current = ""

        if section == "Local Branches":
            if full_branch != current:
                self._switch_branch(full_branch)
        elif section == "Remote Branches":
            local_name = (
                full_branch.split("/", 1)[1] if "/" in full_branch else full_branch
            )
            if local_name != current:
                self._switch_branch_from_remote(full_branch, local_name)

    def _switch_branch(self, branch_name):
        def work():
            self.git.checkout(branch_name)
            return branch_name

        def ok(name):
            self._update_repo_info()
            self._refresh_branch_list()
            if self.changes_dialog and self.changes_dialog.isVisible():
                self.changes_dialog.refresh_contents()
            self._reset_commit_state()
            self.statusBar().showMessage(f"Switched to branch '{name}'")

        def fail(msg):
            self.statusBar().showMessage("Branch switch failed")
            self._show_error("Git Error", msg)

        self.statusBar().showMessage(f"Switching to branch '{branch_name}'...")
        self._run_worker(work, ok, fail)

    def _switch_branch_from_remote(self, remote_branch, local_name):
        def work():
            self.git.checkout_remote(remote_branch, local_name)
            return local_name

        def ok(name):
            self._update_repo_info()
            self._refresh_branch_list()
            if self.changes_dialog and self.changes_dialog.isVisible():
                self.changes_dialog.refresh_contents()
            self._reset_commit_state()
            self.statusBar().showMessage(f"Switched to branch '{name}'")

        def fail(msg):
            self.statusBar().showMessage("Branch switch failed")
            self._show_error("Git Error", msg)

        self.statusBar().showMessage(
            f"Switching to '{local_name}' from '{remote_branch}'..."
        )
        self._run_worker(work, ok, fail)

    # ── Actions ──────────────────────────────────────────────────────

    def _generate_clicked(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "Please select a repository first")
            return

        self._reset_commit_state()

        def work():
            git_info = self.git.get_git_info()
            if not git_info.staged_files or not any(git_info.staged_files):
                raise Exception(
                    "No staged files found. Please stage some files first."
                )
            return self.ai.generate_commit_message(git_info)

        def ok(message):
            self.text_area.setPlainText(message)
            self.commit_btn.setEnabled(True)
            self.statusBar().showMessage("Commit message generated successfully")
            self._update_repo_info()

        def fail(msg):
            self.statusBar().showMessage("Error generating commit message")
            self._show_error("Error", msg)

        self.statusBar().showMessage("Generating commit message...")
        self._run_worker(work, ok, fail)

    def _review_clicked(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "Please select a repository first")
            return

        def work():
            review_info = self.git.get_review_info()
            if not review_info.status_entries:
                raise Exception(
                    "No code changes found. Make some changes before running a review."
                )
            return self.ai.generate_code_review(review_info)

        def ok(review_text):
            self.statusBar().showMessage("AI code review completed")
            dlg = TextDialog(self, "AI Code Review", review_text, markdown=True)
            dlg.exec()

        def fail(msg):
            self.statusBar().showMessage("Error generating AI code review")
            self._show_error("Error", msg)

        self.statusBar().showMessage("Generating AI code review...")
        self._run_worker(work, ok, fail)

    def _root_cause_clicked(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "Please select a repository first")
            return

        # Check for staged changes first
        git_info = self.git.get_git_info()
        has_staged = git_info.staged_files and any(git_info.staged_files)

        if has_staged:
            self._run_root_cause(use_staged=True)
        else:
            self._show_branch_picker()

    def _show_branch_picker(self):
        """Show a dialog to select the branch to compare against."""
        dlg = QDialog(self)
        dlg.setWindowTitle("Root Cause Summary – Select Compare Branch")
        dlg.resize(450, 150)
        lay = QVBoxLayout(dlg)

        lay.addWidget(QLabel(
            "No staged changes found.\n"
            "Select a branch to compare the current branch against:"
        ))

        branch_combo = QComboBox()
        branch_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        branch_combo.setMinimumContentsLength(40)

        # Populate with local and remote branches, default branch pre-selected
        local = self.git.get_local_branches()
        remote = self.git.get_remote_branches()
        current = self.git.get_current_branch()
        default = self.git.get_default_branch()

        all_branches = []
        for b in local:
            if b != current:
                all_branches.append(b)
        for b in remote:
            all_branches.append(b)

        branch_combo.addItems(all_branches)

        # Pre-select the default branch (try remote first, then local)
        preselect = f"origin/{default}" if f"origin/{default}" in all_branches else default
        idx = branch_combo.findText(preselect)
        if idx >= 0:
            branch_combo.setCurrentIndex(idx)

        lay.addWidget(branch_combo)

        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        lay.addWidget(btn_box)

        if dlg.exec() == QDialog.DialogCode.Accepted:
            selected = branch_combo.currentText()
            if selected:
                self._run_root_cause(use_staged=False, compare_branch=selected)

    def _run_root_cause(self, use_staged: bool, compare_branch: str = ""):
        source_label = "staged changes" if use_staged else f"branch diff vs {compare_branch}"

        def work():
            if use_staged:
                git_info = self.git.get_git_info()
            else:
                git_info = self.git.get_branch_diff_info(compare_branch)
                if not git_info.staged_files or not any(git_info.staged_files):
                    raise Exception(
                        f"No differences found between '{compare_branch}' and the current branch."
                    )
            return self.ai.generate_root_cause_summary(git_info)

        def ok(summary_text):
            self.statusBar().showMessage(
                f"Root cause summary generated from {source_label}"
            )
            dlg = TextDialog(
                self, "Root Cause Summary", summary_text, markdown=True
            )
            dlg.exec()

        def fail(msg):
            self.statusBar().showMessage("Error generating root cause summary")
            self._show_error("Error", msg)

        self.statusBar().showMessage("Generating root cause summary...")
        self._run_worker(work, ok, fail)

    def _configure_clicked(self):
        from ui.config_dialog import ConfigDialog

        dlg = ConfigDialog(self, self.config, self.ai)
        if dlg.exec():
            self.ai.setup_clients()
            self._update_api_status()

    def _copy_message(self):
        text = self.text_area.toPlainText().strip()
        if text:
            QApplication.clipboard().setText(text)
            self.statusBar().showMessage("Copied to clipboard")
        else:
            QMessageBox.warning(self, "Warning", "No commit message to copy")

    def _run_commit(self, action: str):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "Please select a repository first")
            return

        message = self.text_area.toPlainText().strip()
        if not message:
            QMessageBox.warning(self, "Warning", "No commit message to use")
            return

        if not self.commit_btn.isEnabled():
            QMessageBox.warning(
                self,
                "Warning",
                "Generate a commit message before running git actions",
            )
            return

        labels = {
            "commit": "Commit Staged Files",
            "push": "Commit and Push",
            "sync": "Commit and Sync",
        }
        label = labels.get(action, "Commit Staged Files")
        self.commit_btn.setEnabled(False)

        def work():
            git_info = self.git.get_git_info()
            if not git_info.staged_files or not any(git_info.staged_files):
                raise Exception(
                    "No staged files found. Please stage some files first."
                )
            self.git.commit(message)
            if action == "push":
                self.git.push()
            elif action == "sync":
                self.git.sync()
            return label

        def ok(lbl):
            self.text_area.clear()
            self._update_repo_info()
            self._refresh_branch_list()
            if self.changes_dialog and self.changes_dialog.isVisible():
                self.changes_dialog.refresh_contents()
            self._reset_commit_state()
            self.statusBar().showMessage(f"{lbl} completed successfully")
            QMessageBox.information(
                self, "Success", f"{lbl} completed successfully."
            )

        def fail(msg):
            self._update_repo_info()
            self.commit_btn.setEnabled(True)
            self.statusBar().showMessage(f"{label} failed")
            self._show_error("Error", msg)

        self.statusBar().showMessage(f"Running {label.lower()}...")
        self._run_worker(work, ok, fail)

    def _manage_repositories(self):
        from ui.repo_manager import RepositoryManager

        dlg = RepositoryManager(self, self.config, self.git)
        dlg.exec()
        self.refresh_repositories()

    def _open_changes(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "Please select a repository first")
            return

        from ui.changes_dialog import ChangesDialog

        if self.changes_dialog and self.changes_dialog.isVisible():
            self.changes_dialog.raise_()
            self.changes_dialog.activateWindow()
            self.changes_dialog.refresh_contents()
            return

        self.changes_dialog = ChangesDialog(self, self.git)
        self.changes_dialog.show()

    def _refresh_status(self):
        if self.current_repo_path:
            self.statusBar().showMessage("Refreshing repository status...")
            self._update_repo_info()
            self._refresh_branch_list()
            if self.changes_dialog and self.changes_dialog.isVisible():
                self.changes_dialog.refresh_contents()
            self._reset_commit_state()
            self.statusBar().showMessage("Repository status refreshed")
        else:
            self.statusBar().showMessage("No repository selected")

    def _open_terminal(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "No repository selected")
            return
        try:
            system = platform.system()
            if system == "Windows":
                subprocess.run(
                    ["start", "powershell"],
                    cwd=self.current_repo_path,
                    shell=True,
                )
            elif system == "Darwin":
                subprocess.run(
                    ["open", "-a", "Terminal", self.current_repo_path]
                )
            else:
                subprocess.run(["xdg-open", self.current_repo_path])
        except Exception as e:
            self._show_error("Error", f"Could not open terminal: {e}")

    def _open_explorer(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "No repository selected")
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.current_repo_path))

    def _raise_pull_request(self):
        if not self.current_repo_path:
            QMessageBox.warning(self, "Warning", "No repository selected")
            return
        git = self.git
        remote_url = git.get_remote_url()
        if not remote_url:
            QMessageBox.warning(
                self, "Warning", "No remote URL found for this repository."
            )
            return

        # Convert remote URL to a GitHub HTTPS base URL.
        # Handles HTTPS (https://github.com/owner/repo.git)
        # and SSH  (git@github.com:owner/repo.git) formats.
        m = re.match(r"git@([^:]+):(.+?)(?:\.git)?$", remote_url)
        if m:
            host, path = m.group(1), m.group(2)
            base_url = f"https://{host}/{path}"
        else:
            base_url = re.sub(r"\.git$", "", remote_url)

        try:
            branch = git.get_current_branch()
        except Exception:
            QMessageBox.warning(
                self, "Warning", "Could not determine the current branch."
            )
            return

        pr_url = f"{base_url}/compare/{branch}?expand=1"
        QDesktopServices.openUrl(QUrl(pr_url))

    # ── Package checking ─────────────────────────────────────────────

    def _check_packages(self):
        missing = self.ai.get_missing_packages()
        if not missing:
            return
        pip_name, display_name = missing[0]
        result = QMessageBox.question(
            self,
            "Missing Packages",
            f"The {display_name} package is required but not installed.\n\n"
            "Would you like to install it now?",
        )
        if result == QMessageBox.StandardButton.Yes:
            self._install_package(pip_name, display_name)

    def _install_package(self, pip_name, display_name):
        progress = QProgressDialog(
            f"Installing {display_name}...", None, 0, 0, self
        )
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.show()

        def work():
            AIService.install_package(pip_name)

        def ok(_):
            progress.close()
            QMessageBox.information(
                self,
                "Installation Complete",
                "Package installed successfully.\n"
                "Please restart the application to use the new package.",
            )

        def fail(msg):
            progress.close()
            self._show_error(
                "Installation Failed",
                f"Failed to install {display_name}: {msg}",
            )

        self._run_worker(work, ok, fail)

    # ── Helpers ──────────────────────────────────────────────────────

    def _show_error(self, title, message):
        dlg = TextDialog(self, title, message)
        dlg.exec()

    def _run_worker(self, fn, on_success, on_error):
        thread = WorkerThread(fn, parent=self)
        thread.result_ready.connect(on_success)
        thread.error_occurred.connect(on_error)
        thread.finished.connect(thread.deleteLater)
        thread.start()
        self._active_thread = thread
