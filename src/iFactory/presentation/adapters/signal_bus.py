"""
Signal Bus - Application-wide signal management.

Provides a singleton for cross-cutting signal communication.
Used for components that need to communicate without direct coupling.
"""

import logging
from typing import Any, Dict

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class SignalBus(QObject):
    """
    Singleton signal bus for application-wide events.

    Use sparingly - prefer direct ViewModel signals for component communication.
    This is mainly for truly cross-cutting concerns.
    """

    # Core signals
    devices_updated = Signal(dict)
    gantt_updated = Signal(dict)
    error_occurred = Signal(str)
    loading_changed = Signal(bool)
    theme_changed = Signal(str)

    # Navigation signals
    page_changed = Signal(str)
    device_selected = Signal(str)
    device_deselected = Signal()

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
        logger.debug("[SignalBus] Initialized")

    def emit_devices(self, data: Dict[str, Any]) -> None:
        """Emit device update signal."""
        self.devices_updated.emit(data)

    def emit_gantt(self, data: Dict[str, Any]) -> None:
        """Emit gantt update signal."""
        self.gantt_updated.emit(data)

    def emit_error(self, message: str) -> None:
        """Emit error signal."""
        logger.error(f"[SignalBus] Error: {message}")
        self.error_occurred.emit(message)

    def emit_loading(self, is_loading: bool) -> None:
        """Emit loading state signal."""
        self.loading_changed.emit(is_loading)

    def emit_theme(self, theme: str) -> None:
        """Emit theme change signal."""
        self.theme_changed.emit(theme)

    def emit_page_change(self, page: str) -> None:
        """Emit page change signal."""
        self.page_changed.emit(page)

    def emit_device_selected(self, device_id: str) -> None:
        """Emit device selection signal."""
        self.device_selected.emit(device_id)

    def emit_device_deselected(self) -> None:
        """Emit device deselection signal."""
        self.device_deselected.emit()


def get_signal_bus() -> SignalBus:
    """Get the singleton signal bus instance."""
    return SignalBus()


__all__ = ["SignalBus", "get_signal_bus"]
