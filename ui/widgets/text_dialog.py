"""Reusable dialog for displaying text or markdown with copy support."""

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QApplication,
)


class TextDialog(QDialog):
    """Modal dialog that shows read-only text with a copy-to-clipboard button."""

    def __init__(self, parent, title: str, content: str, markdown: bool = False):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(700, 420)
        self.setMinimumSize(500, 300)

        layout = QVBoxLayout(self)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        if markdown:
            self.text_edit.setMarkdown(content)
        else:
            self.text_edit.setPlainText(content)
        layout.addWidget(self.text_edit, stretch=1)

        btn_row = QHBoxLayout()
        self._copy_btn = QPushButton("Copy to Clipboard")
        self._copy_btn.clicked.connect(self._copy)
        btn_row.addWidget(self._copy_btn)
        btn_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _copy(self):
        QApplication.clipboard().setText(self.text_edit.toPlainText())
        self._copy_btn.setText("Copied!")
        from PySide6.QtCore import QTimer

        QTimer.singleShot(1500, lambda: self._copy_btn.setText("Copy to Clipboard"))
