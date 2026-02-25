import logging
import os
from PySide6.QtCore import QObject, Signal


class AppLogger(QObject):
    log_signal = Signal(str, str)  # (message, level)

    def __init__(self, base_dir: str):
        super().__init__()
        log_dir = os.path.join(base_dir, "logs")
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(
                    os.path.join(log_dir, "a1d_upscaler.log"),
                    encoding="utf-8"
                )
            ]
        )
        self._logger = logging.getLogger("A1DUpscaler")

    def info(self, msg: str):
        self._logger.info(msg)
        self.log_signal.emit(msg, "INFO")

    def warning(self, msg: str):
        self._logger.warning(msg)
        self.log_signal.emit(msg, "WARNING")

    def error(self, msg: str):
        self._logger.error(msg)
        self.log_signal.emit(msg, "ERROR")

    def success(self, msg: str):
        self._logger.info(f"[SUCCESS] {msg}")
        self.log_signal.emit(msg, "SUCCESS")


_instance = None


def get_logger(base_dir: str = None) -> AppLogger:
    global _instance
    if _instance is None and base_dir:
        _instance = AppLogger(base_dir)
    return _instance
