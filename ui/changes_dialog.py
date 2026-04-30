"""Modeless dialog showing changed files and their diffs."""

from typing import List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from core.git_service import GitService
from core.models import StatusEntry
from ui.widgets.diff_viewer import DiffViewer


class ChangesDialog(QDialog):
    """Modeless dialog showing changed files and diffs for a repository."""

    def __init__(self, parent, git: GitService):
        super().__init__(parent)
        self.main_window = parent
        self.git = git
        self.status_entries: List[StatusEntry] = []

        self.setWindowTitle("Repository Changes")
        self.resize(1120, 720)
        self.setMinimumSize(860, 520)
        # Keep modeless – don't set WindowModal
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)

        self._setup_ui()
        self.refresh_contents()

    # ── UI construction ──────────────────────────────────────────────

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Toolbar
        toolbar = QHBoxLayout()
        self.summary_label = QLabel("Loading changes...")
        toolbar.addWidget(self.summary_label)
        toolbar.addStretch()

        self.stage_btn = QPushButton("Stage Selected")
        self.stage_btn.setEnabled(False)
        self.stage_btn.clicked.connect(self._stage_selected)
        toolbar.addWidget(self.stage_btn)

        self.unstage_btn = QPushButton("Unstage Selected")
        self.unstage_btn.setEnabled(False)
        self.unstage_btn.clicked.connect(self._unstage_selected)
        toolbar.addWidget(self.unstage_btn)

        self.discard_btn = QPushButton("Discard Unstaged")
        self.discard_btn.setEnabled(False)
        self.discard_btn.clicked.connect(self._discard_selected)
        toolbar.addWidget(self.discard_btn)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_contents)
        toolbar.addWidget(refresh_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        toolbar.addWidget(close_btn)

        layout.addLayout(toolbar)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left – file list
        left = QWidget()
        left_lay = QVBoxLayout(left)
        left_lay.setContentsMargins(0, 0, 0, 0)
        left_lay.addWidget(QLabel("Changed Files"))

        self.files_list = QListWidget()
        self.files_list.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.files_list.itemSelectionChanged.connect(self._on_selection_changed)
        left_lay.addWidget(self.files_list)

        hint = QLabel("Tip: use Ctrl/Shift to select multiple files.")
        hint.setStyleSheet("color: gray;")
        left_lay.addWidget(hint)

        splitter.addWidget(left)

        # Right – diff viewer
        right = QWidget()
        right_lay = QVBoxLayout(right)
        right_lay.setContentsMargins(0, 0, 0, 0)
        self.diff_title = QLabel("Diff Preview")
        right_lay.addWidget(self.diff_title)
        self.diff_viewer = DiffViewer()
        right_lay.addWidget(self.diff_viewer)

        splitter.addWidget(right)
        splitter.setSizes([300, 820])

        layout.addWidget(splitter, stretch=1)

    # ── Refresh ──────────────────────────────────────────────────────

    def refresh_contents(self):
        selected_paths = {e.path for e in self._selected_entries()}

        try:
            self.status_entries = self.git.get_status_entries()
        except Exception as exc:
            self.status_entries = []
            self.summary_label.setText("Unable to load changes")
            self.diff_viewer.set_segments([(str(exc), "note")])
            self.files_list.clear()
            self._update_buttons()
            return

        self.files_list.clear()
        for entry in self.status_entries:
            item = QListWidgetItem(self._format_label(entry))
            item.setForeground(self._color_for(entry))
            self.files_list.addItem(item)

        staged = sum(1 for e in self.status_entries if e.has_staged)
        unstaged = sum(1 for e in self.status_entries if e.has_unstaged)
        self.summary_label.setText(
            f"{len(self.status_entries)} changed file(s) | "
            f"Staged: {staged} | Unstaged: {unstaged}"
        )

        # Restore selection
        restored = False
        for i, entry in enumerate(self.status_entries):
            if entry.path in selected_paths:
                self.files_list.item(i).setSelected(True)
                restored = True

        if self.status_entries and not restored:
            self.files_list.item(0).setSelected(True)

        self._render_selected_diffs()
        self._update_buttons()

    # ── Selection ────────────────────────────────────────────────────

    def _selected_entries(self) -> List[StatusEntry]:
        return [
            self.status_entries[idx.row()]
            for idx in self.files_list.selectedIndexes()
        ]

    def _on_selection_changed(self):
        self._render_selected_diffs()
        self._update_buttons()

    def _update_buttons(self):
        entries = self._selected_entries()
        self.stage_btn.setEnabled(any(e.has_unstaged for e in entries))
        self.unstage_btn.setEnabled(any(e.has_staged for e in entries))
        self.discard_btn.setEnabled(
            any(e.has_unstaged and not e.has_staged for e in entries)
        )

    # ── Diff rendering ───────────────────────────────────────────────

    def _render_selected_diffs(self):
        selected = self._selected_entries()

        if not self.status_entries:
            self.diff_title.setText("Diff Preview")
            self.diff_viewer.set_segments(
                [("No changed files in this repository.\n", "note")]
            )
            return

        if not selected:
            self.diff_title.setText("Diff Preview")
            self.diff_viewer.set_segments(
                [("Select a file to preview its diff.\n", "note")]
            )
            return

        self.diff_title.setText(f"Diff Preview ({len(selected)} selected)")

        segments = []
        for entry in selected:
            segments.append((f"{self._format_label(entry)}\n", "file_title"))

            sections = self.git.get_file_diff_sections(entry, context_lines=4)
            if not sections:
                segments.append(
                    ("No diff available for this file.\n\n", "note")
                )
                continue

            for title, diff_text in sections:
                segments.append((f"{title}\n", "section_title"))
                segments.extend(DiffViewer.colorize_diff(diff_text))
                segments.append(("\n", None))

            segments.append(("\n", None))

        self.diff_viewer.set_segments(segments)

    # ── Stage / unstage / discard ────────────────────────────────────

    def _stage_selected(self):
        targets = [e for e in self._selected_entries() if e.has_unstaged]
        if not targets:
            return
        try:
            for e in targets:
                self.git.stage_file(e.path)
        except Exception as exc:
            self._show_error("Stage Failed", str(exc))
            return
        self.main_window._update_repo_info()
        self.main_window._reset_commit_state()
        self.main_window.statusBar().showMessage(
            f"Staged {len(targets)} file(s)"
        )
        self.refresh_contents()

    def _unstage_selected(self):
        targets = [e for e in self._selected_entries() if e.has_staged]
        if not targets:
            return
        try:
            for e in targets:
                self.git.unstage_file(e.path)
        except Exception as exc:
            self._show_error("Unstage Failed", str(exc))
            return
        self.main_window._update_repo_info()
        self.main_window._reset_commit_state()
        self.main_window.statusBar().showMessage(
            f"Unstaged {len(targets)} file(s)"
        )
        self.refresh_contents()

    def _discard_selected(self):
        targets = [
            e
            for e in self._selected_entries()
            if e.has_unstaged and not e.has_staged
        ]
        if not targets:
            return

        file_list = "\n".join(f"  - {e.display_path}" for e in targets)
        result = QMessageBox.question(
            self,
            "Discard Unstaged Changes",
            "This will permanently discard unstaged changes for the "
            "selected files.\n\n"
            f"{file_list}\n\n"
            "Files with staged changes are not affected.",
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            for e in targets:
                self.git.discard_unstaged_changes(e)
        except Exception as exc:
            self._show_error("Discard Failed", str(exc))
            return

        self.main_window._update_repo_info()
        self.main_window._reset_commit_state()
        self.main_window.statusBar().showMessage(
            f"Discarded unstaged changes in {len(targets)} file(s)"
        )
        self.refresh_contents()

    # ── Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _format_label(entry: StatusEntry) -> str:
        flags = []
        if entry.has_staged:
            flags.append("S")
        if entry.has_unstaged:
            flags.append("U")
        if entry.is_untracked:
            flags.append("NEW")
        flag_text = "/".join(flags) if flags else "-"
        return f"[{flag_text}] {entry.display_path}"

    @staticmethod
    def _color_for(entry: StatusEntry) -> QColor:
        if entry.has_staged and entry.has_unstaged:
            return QColor("#1d4ed8")
        if entry.has_staged:
            return QColor("#15803d")
        return QColor("#b45309")

    def _show_error(self, title, message):
        from ui.widgets.text_dialog import TextDialog

        dlg = TextDialog(self, title, message)
        dlg.exec()
