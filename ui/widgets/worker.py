"""Background thread helper for long-running operations."""

from PySide6.QtCore import QThread, Signal


class WorkerThread(QThread):
    """Run a callable in a background thread, emitting results via signals."""

    result_ready = Signal(object)
    error_occurred = Signal(str)

    def __init__(self, fn, *args, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._args = args

    def run(self):
        try:
            result = self._fn(*self._args)
            self.result_ready.emit(result)
        except Exception as exc:
            self.error_occurred.emit(str(exc))
