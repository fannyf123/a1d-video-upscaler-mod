from PySide6.QtCore import QObject, Signal


class ProgressHandler(QObject):
    progress_updated = Signal(int, str)   # (percent, message)
    task_completed   = Signal(bool, str)  # (success, message)

    def __init__(self):
        super().__init__()
        self._current = 0

    def update(self, percent: int, message: str = ""):
        self._current = max(0, min(100, percent))
        self.progress_updated.emit(self._current, message)

    def complete(self, success: bool, message: str = ""):
        self.task_completed.emit(success, message)

    @property
    def current(self) -> int:
        return self._current
