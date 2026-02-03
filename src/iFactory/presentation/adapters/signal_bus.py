"""
Signal Bus - Application-wide signal management with throttling.

Provides a singleton for cross-cutting signal communication.
High-frequency signals are throttled to prevent UI freezing.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)


class SignalThrottler(QObject):
    """
    Throttles high-frequency signal emissions.

    Batches updates and emits at most once per interval.
    """

    flushed = Signal(object)

    def __init__(self, interval_ms: int = 50, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._interval_ms = interval_ms
        self._pending_data: Optional[Any] = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._flush)

    def push(self, data: Any) -> None:
        """Push data to be emitted (batched)."""
        self._pending_data = data
        if not self._timer.isActive():
            self._timer.start(self._interval_ms)

    def _flush(self) -> None:
        """Emit batched data."""
        if self._pending_data is not None:
            self.flushed.emit(self._pending_data)
            self._pending_data = None

    def flush_now(self) -> None:
        """Force immediate flush."""
        self._timer.stop()
        self._flush()

    def cancel(self) -> None:
        """Cancel pending emission."""
        self._timer.stop()
        self._pending_data = None


class SignalBus(QObject):
    """
    Singleton signal bus for application-wide events.

    High-frequency signals (devices_updated, gantt_updated) are
    automatically throttled to prevent UI freezing.

    Throttle interval: 50ms (20 FPS max)
    """

    devices_updated = Signal(dict)
    gantt_updated = Signal(dict)
    error_occurred = Signal(str)
    loading_changed = Signal(bool)
    theme_changed = Signal(str)
    page_changed = Signal(str)
    device_selected = Signal(str)
    device_deselected = Signal()

    THROTTLE_INTERVAL_MS = 50

    _instance: Optional["SignalBus"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized") and self._initialized:
            return
        super().__init__()
        self._initialized = True

        self._devices_throttler = SignalThrottler(self.THROTTLE_INTERVAL_MS, self)
        self._devices_throttler.flushed.connect(self._emit_devices_internal)

        self._gantt_throttler = SignalThrottler(self.THROTTLE_INTERVAL_MS, self)
        self._gantt_throttler.flushed.connect(self._emit_gantt_internal)

        logger.debug("[SignalBus] Initialized with throttling")

    def _emit_devices_internal(self, data: Dict[str, Any]) -> None:
        """Internal: emit after throttle."""
        self.devices_updated.emit(data)

    def _emit_gantt_internal(self, data: Dict[str, Any]) -> None:
        """Internal: emit after throttle."""
        self.gantt_updated.emit(data)

    def emit_devices(self, data: Dict[str, Any]) -> None:
        """Emit device update signal (throttled)."""
        self._devices_throttler.push(data)

    def emit_devices_immediate(self, data: Dict[str, Any]) -> None:
        """Emit device update immediately (bypasses throttle)."""
        self._devices_throttler.flush_now()
        self.devices_updated.emit(data)

    def emit_gantt(self, data: Dict[str, Any]) -> None:
        """Emit gantt update signal (throttled)."""
        self._gantt_throttler.push(data)

    def emit_gantt_immediate(self, data: Dict[str, Any]) -> None:
        """Emit gantt update immediately (bypasses throttle)."""
        self._gantt_throttler.flush_now()
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

    def flush_all(self) -> None:
        """Force flush all throttled signals."""
        self._devices_throttler.flush_now()
        self._gantt_throttler.flush_now()


def get_signal_bus() -> SignalBus:
    """Get the singleton signal bus instance."""
    return SignalBus()


__all__ = ["SignalBus", "SignalThrottler", "get_signal_bus"]
