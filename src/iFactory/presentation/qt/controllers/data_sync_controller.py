"""
Data Sync Controller - Handles data synchronization.

Coordinates:
    - Periodic sync scheduling
    - Manual sync requests
    - Sync status reporting
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional
from PySide6.QtCore import QObject, QTimer, Signal

if TYPE_CHECKING:
    from iFactory.application.services.__init__1 import DeviceDataService
    from iFactory.presentation.adapters import AsyncExecutor, QtSignalAdapter
logger = logging.getLogger(__name__)


class DataSyncController(QObject):
    """
    Controller for data synchronization.

    Responsibilities:
        - Schedule periodic syncs
        - Handle manual sync requests
        - Report sync status
        - Coordinate with signal adapter
    """

    sync_started = Signal()
    sync_completed = Signal(int)
    sync_failed = Signal(str)
    DEFAULT_SYNC_INTERVAL = 5000

    def __init__(
        self,
        data_service: "DeviceDataService",
        async_executor: "AsyncExecutor",
        signal_adapter: Optional["QtSignalAdapter"] = None,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize sync controller.

        Args:
            data_service: Device data service
            async_executor: Async executor
            signal_adapter: Qt signal adapter
            parent: Qt parent
        """
        super().__init__(parent)
        self._service = data_service
        self._executor = async_executor
        self._adapter = signal_adapter
        self._sync_timer = QTimer(self)
        self._sync_timer.timeout.connect(self._on_sync_timer)
        self._is_syncing = False
        self._last_sync_count = 0
        self._sync_interval = self.DEFAULT_SYNC_INTERVAL

    def start_periodic_sync(self, interval_ms: Optional[int] = None, immediate: bool = True) -> None:
        """
        Start periodic synchronization.

        Args:
            interval_ms: Sync interval (default: 5000ms)
            immediate: Run sync immediately
        """
        self._sync_interval = interval_ms or self.DEFAULT_SYNC_INTERVAL
        self._sync_timer.setInterval(self._sync_interval)
        if immediate:
            self.sync_now()
        self._sync_timer.start()
        logger.info(f"Periodic sync started ({self._sync_interval}ms)")

    def stop_periodic_sync(self) -> None:
        """Stop periodic synchronization."""
        self._sync_timer.stop()
        logger.info("Periodic sync stopped")

    def set_sync_interval(self, interval_ms: int) -> None:
        """
        Update sync interval.

        Args:
            interval_ms: New interval in milliseconds
        """
        self._sync_interval = max(1000, interval_ms)
        if self._sync_timer.isActive():
            self._sync_timer.setInterval(self._sync_interval)

    @property
    def is_syncing(self) -> bool:
        """Check if sync is in progress."""
        return self._is_syncing

    @property
    def is_periodic_active(self) -> bool:
        """Check if periodic sync is active."""
        return self._sync_timer.isActive()

    def sync_now(self, equipment_codes: Optional[List[str]] = None) -> None:
        """
        Trigger immediate sync.

        Args:
            equipment_codes: Optional list of devices to sync
        """
        if self._is_syncing:
            logger.debug("Sync already in progress")
            return
        self._is_syncing = True
        self.sync_started.emit()
        if self._adapter:
            self._adapter.emit_sync_started()

        async def _do_sync():
            try:
                count = await self._service.sync_device_status(equipment_codes)
                return count
            except Exception as e:
                logger.error(f"Sync failed: {e}")
                raise

        self._executor.run(
            _do_sync(),
            callback=self._on_sync_success,
            error_callback=self._on_sync_error,
        )

    def _on_sync_timer(self) -> None:
        """Handle sync timer tick."""
        self.sync_now()

    def _on_sync_success(self, count: int) -> None:
        """Handle successful sync."""
        self._is_syncing = False
        self._last_sync_count = count
        self.sync_completed.emit(count)
        if self._adapter:
            self._adapter.emit_sync_completed(count)
        logger.debug(f"Sync completed: {count} devices")

    def _on_sync_error(self, error: Exception) -> None:
        """Handle sync error."""
        self._is_syncing = False
        error_msg = str(error)
        self.sync_failed.emit(error_msg)
        if self._adapter:
            self._adapter.emit_error("sync", error_msg)
        logger.error(f"Sync error: {error_msg}")

    def request_gantt_data(self, device_code: str, frame_name: str) -> None:
        """
        Request Gantt chart data.

        Args:
            device_code: Device identifier
            frame_name: Target frame name
        """

        async def _fetch():
            segments = await self._service.get_gantt_segments(device_code)
            return (device_code, frame_name, segments)

        def _on_success(result):
            (code, frame, segments) = result
            if self._adapter and segments:
                from datetime import datetime

                now = datetime.now()
                start = now.replace(hour=0, minute=0, second=0, microsecond=0)
                self._adapter.emit_gantt_data(
                    code,
                    [(s.start_time, s.end_time, s.status_name) for s in segments],
                    start,
                    now,
                )

        self._executor.run(_fetch(), callback=_on_success)

    def request_device_history(self, device_code: str, history_type: str, days: int = 7) -> None:
        """
        Request device history data.

        Args:
            device_code: Device identifier
            history_type: Type of history (status, input, output)
            days: Number of days
        """
        logger.debug(f"History request: {device_code} - {history_type}")

    def request_summary_data(self, devices: List[str], days: int = 7) -> None:
        """
        Request summary data for devices.

        Args:
            devices: List of device codes
            days: Number of days
        """
        logger.debug(f"Summary request: {len(devices)} devices")

    def get_status(self) -> Dict[str, Any]:
        """Get sync controller status."""
        return {
            "is_syncing": self._is_syncing,
            "is_periodic": self.is_periodic_active,
            "interval_ms": self._sync_interval,
            "last_count": self._last_sync_count,
            "online": self._service.is_online(),
        }

    def dispose(self) -> None:
        """Clean up resources."""
        self.stop_periodic_sync()
        logger.debug("DataSyncController disposed")


__all__ = ["DataSyncController"]
