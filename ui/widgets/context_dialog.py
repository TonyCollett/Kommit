"""Dialog for entering additional context for AI code review."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QTextEdit,
    QDialogButtonBox,
    QWidget,
)


class ContextDialog(QDialog):
    """Modal dialog for entering additional context before AI code review."""

    def __init__(self, parent=None, title: str = "Additional Context"):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 400)
        self.setMinimumSize(500, 300)

        layout = QVBoxLayout(self)

        # Instructions label
        hint = QLabel(
            "Provide additional context about the changes to help the AI "
            "understand the intent, purpose, or specific areas of concern."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; margin-bottom: 8px;")
        layout.addWidget(hint)

        # Context text editor
        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText(
            "Enter context here...\n\n"
            "Examples:\n"
            "- This change implements user authentication using JWT tokens\n"
            "- Refactoring the database layer to use async queries\n"
            "- Fixing a bug where users couldn't log in with special characters\n"
            "- Performance optimization for the search endpoint"
        )
        layout.addWidget(self.text_edit, stretch=1)

        # Character count label
        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setStyleSheet("color: gray; font-size: 10px;")
        self.text_edit.textChanged.connect(self._update_char_count)
        layout.addWidget(self.char_count_label)

        # Button box
        btn_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    def _update_char_count(self):
        count = len(self.text_edit.toPlainText())
        self.char_count_label.setText(f"{count} characters")

    def get_context(self) -> str:
        """Return the entered context text, stripped of leading/trailing whitespace."""
        return self.text_edit.toPlainText().strip()

    @staticmethod
    def get_context_from_user(parent=None) -> str | None:
        """Show dialog and return context text if accepted, None if cancelled."""
        dlg = ContextDialog(parent)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            return dlg.get_context()
        return None
