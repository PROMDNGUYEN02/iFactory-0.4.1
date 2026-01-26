"""
Qt Signal Adapter.
Safely bridges background thread events to the Qt Main Event Loop.
"""

import logging
from PySide6.QtCore import QObject, Signal
from typing import Any, Dict

logger = logging.getLogger(__name__)


class QtSignalAdapter(QObject):
    """
    Emits signals from background threads so they can be processed
    safely on the main GUI thread.
    """

    # Define signals that the Redux Store or Controllers will listen to
    device_status_updated = Signal(dict)
    system_error_occurred = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        logger.debug("[QtSignalAdapter] Initialized.")

    def emit_device_statuses(self, status_data: Dict[str, Any]) -> None:
        """Called by background workers to push new device states."""
        self.device_status_updated.emit(status_data)

    def emit_error(self, error_message: str) -> None:
        """Called by background workers to push errors."""
        self.system_error_occurred.emit(error_message)


__all__ = ["QtSignalAdapter"]
