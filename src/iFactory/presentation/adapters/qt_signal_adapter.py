"""
Qt Signal Adapter.
Bridges background thread events to Qt Main Event Loop.
"""

import logging
from typing import Any, Dict

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class QtSignalAdapter(QObject):
    """Emits signals from background threads for main thread processing."""

    device_status_updated = Signal(dict)
    system_error_occurred = Signal(str)
    loading_state_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)

    def emit_device_statuses(self, status_data: Dict[str, Any]) -> None:
        self.device_status_updated.emit(status_data)

    def emit_error(self, error_message: str) -> None:
        self.system_error_occurred.emit(error_message)

    def emit_loading(self, is_loading: bool) -> None:
        self.loading_state_changed.emit(is_loading)


__all__ = ["QtSignalAdapter"]
