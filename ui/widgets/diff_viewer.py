"""Read-only diff viewer with syntax-coloured segments."""

from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit


class DiffViewer(QTextEdit):
    """Rich-text diff viewer that renders pre-tagged segments."""

    # tag  →  format spec
    _TAG_SPECS = {
        "file_title": {"bold": True, "size_delta": 1},
        "section_title": {"fg": "#6b7280", "spacing": True},
        "diff_meta": {"fg": "#1d4ed8"},
        "hunk": {"fg": "#7c3aed"},
        "added": {"fg": "#15803d"},
        "removed": {"fg": "#b91c1c"},
        "note": {"fg": "#6b7280", "italic": True},
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setLineWrapMode(QTextEdit.LineWrapMode.NoWrap)
        self._init_font()

    def _init_font(self):
        for family in ("Cascadia Code", "Consolas", "Courier New"):
            font = QFont(family, 10)
            if font.exactMatch():
                self.setFont(font)
                self._base_size = font.pointSize()
                return
        font = QFont()
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setPointSize(10)
        self.setFont(font)
        self._base_size = 10

    # ── Public API ───────────────────────────────────────────────────

    def set_segments(self, segments: List[Tuple[str, Optional[str]]]):
        """Replace content with a list of ``(text, tag | None)`` segments."""
        self.clear()
        cursor = self.textCursor()
        for text, tag in segments:
            fmt = self._format_for(tag)
            cursor.insertText(text, fmt)
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.setTextCursor(cursor)

    # ── Diff colouring utility ───────────────────────────────────────

    @staticmethod
    def colorize_diff(diff_text: str) -> List[Tuple[str, Optional[str]]]:
        """Split raw diff text into tagged ``(line, tag)`` segments."""
        segments: List[Tuple[str, Optional[str]]] = []
        for line in diff_text.splitlines(keepends=True):
            tag = None
            if line.startswith("diff --git"):
                tag = "diff_meta"
            elif line.startswith((
                "index ", "new file mode", "deleted file mode",
                "similarity index", "rename from ", "rename to ",
                "copy from ", "copy to ", "--- ", "+++ ",
            )):
                tag = "diff_meta"
            elif line.startswith("@@"):
                tag = "hunk"
            elif line.startswith("+") and not line.startswith("+++"):
                tag = "added"
            elif line.startswith("-") and not line.startswith("---"):
                tag = "removed"
            elif line.startswith("\\"):
                tag = "note"
            segments.append((line, tag))
        return segments

    # ── Internal helpers ─────────────────────────────────────────────

    def _format_for(self, tag: Optional[str]) -> QTextCharFormat:
        fmt = QTextCharFormat()
        fmt.setFont(self.font())
        if tag and tag in self._TAG_SPECS:
            spec = self._TAG_SPECS[tag]
            if "fg" in spec:
                fmt.setForeground(QColor(spec["fg"]))
            if spec.get("bold"):
                fmt.setFontWeight(QFont.Weight.Bold)
            if spec.get("italic"):
                fmt.setFontItalic(True)
            if "size_delta" in spec:
                fmt.setFontPointSize(self._base_size + spec["size_delta"])
        return fmt
