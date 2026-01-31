# File: presentation/adapters/signal_bus.py
import logging
from typing import Any, Dict

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class SignalBus(QObject):
    devices_updated = Signal(dict)
    gantt_updated = Signal(dict)
    error_occurred = Signal(str)
    loading_changed = Signal(bool)
    theme_changed = Signal(str)

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__()
        self._initialized = True

    def emit_devices(self, data: Dict[str, Any]) -> None:
        self.devices_updated.emit(data)

    def emit_gantt(self, data: Dict[str, Any]) -> None:
        self.gantt_updated.emit(data)

    def emit_error(self, message: str) -> None:
        logger.error(f"SignalBus error: {message}")
        self.error_occurred.emit(message)

    def emit_loading(self, is_loading: bool) -> None:
        self.loading_changed.emit(is_loading)

    def emit_theme(self, theme: str) -> None:
        self.theme_changed.emit(theme)


def get_signal_bus() -> SignalBus:
    return SignalBus()


__all__ = ["SignalBus", "get_signal_bus"]
