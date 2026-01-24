# File: presentation/adapters/qt_signal_adapter.py
"""
Qt Signal Adapter - Bridge async services with Qt signals.

Provides type-safe signal emission from async context.
"""
from __future__ import annotations
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import random
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class DeviceSignals(QObject):
    """
    Qt signals for device-related events.

    Signals:
        device_statuses_updated: Batch status update
        device_status_changed: Single device status change
        gantt_data_ready: Gantt chart data available
        table_data_ready: Table data available
        summary_data_ready: Summary data available
        sync_completed: Sync operation completed
        error_occurred: Error occurred
    """

    device_statuses_updated = Signal(dict)
    device_status_changed = Signal(str, str)
    gantt_data_ready = Signal(str, list, object, object)
    table_data_ready = Signal(dict)
    summary_data_ready = Signal(list)
    sync_completed = Signal(int)
    sync_started = Signal()
    error_occurred = Signal(str, str)


class QtSignalAdapter:
    """
    Adapter to emit Qt signals from async services.

    Thread-safe signal emission for async operations.

    Example:
        adapter = QtSignalAdapter()

        # In async code:
        await service.sync()
        adapter.emit_sync_completed(count)

        # Set gantt provider:
        adapter.set_gantt_provider(device_service)
    """

    def __init__(self):
        """Initialize adapter with signal holder."""
        self._signals = DeviceSignals()
        self._gantt_provider: Optional[Any] = None

    @property
    def signals(self) -> DeviceSignals:
        """Get signal holder for connection."""
        return self._signals

    def set_gantt_provider(self, provider: Any) -> None:
        """
        Set the Gantt data provider.

        Provider should have method: get_device_history(device_code, start, end) -> List[segments]

        Args:
            provider: Object that provides Gantt data (typically DeviceDataService)
        """
        self._gantt_provider = provider
        logger.debug(f"[QtSignalAdapter] Gantt provider set: {(type(provider).__name__ if provider else None)}")

    def get_gantt_provider(self) -> Optional[Any]:
        """Get current Gantt provider."""
        return self._gantt_provider

    def has_gantt_provider(self) -> bool:
        """Check if Gantt provider is configured."""
        return self._gantt_provider is not None

    def request_gantt_data(self, device_code: str, frame_name: str) -> None:
        """
        Request Gantt data for a device.

        This is called by MainView when it needs Gantt data.

        Args:
            device_code: Device code to get data for
            frame_name: Frame name requesting the data
        """
        logger.info(f"[QtSignalAdapter] request_gantt_data: device={device_code}, frame={frame_name}")
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=24)
        segments = []
        if self._gantt_provider:
            try:
                if hasattr(self._gantt_provider, "get_device_history"):
                    raw_data = self._gantt_provider.get_device_history(device_code, start_time, end_time)
                    segments = self._convert_to_segments(raw_data, start_time, end_time)
                elif hasattr(self._gantt_provider, "get_segments"):
                    segments = self._gantt_provider.get_segments(device_code, start_time, end_time)
                logger.debug(f"[QtSignalAdapter] Got {len(segments)} segments from provider")
            except Exception as e:
                logger.error(f"[QtSignalAdapter] Gantt provider error: {e}")
        else:
            segments = self._generate_demo_segments(start_time, end_time)
            logger.debug(f"[QtSignalAdapter] Generated {len(segments)} demo segments")
        self._signals.gantt_data_ready.emit(device_code, segments, start_time, end_time)

    def _convert_to_segments(self, raw_data: List[Any], start_time: datetime, end_time: datetime) -> List[Tuple[datetime, datetime, str]]:
        """Convert raw data to segment tuples (start, end, status)."""
        segments = []
        if not raw_data:
            return segments
        for item in raw_data:
            try:
                get_val = lambda key, default=None: (getattr(item, key, default) if hasattr(item, key) else item.get(key, default))
                seg_start = get_val("start_time") or get_val("timestamp")
                seg_end = get_val("end_time")
                status = get_val("status") or get_val("status_name", "unknown")
                if isinstance(seg_start, str):
                    seg_start = datetime.fromisoformat(seg_start)
                if isinstance(seg_end, str):
                    seg_end = datetime.fromisoformat(seg_end)
                if seg_start and seg_end:
                    segments.append((seg_start, seg_end, str(status)))
            except Exception as e:
                logger.debug(f"Segment conversion error: {e}")
        return segments

    def _generate_demo_segments(self, start_time: datetime, end_time: datetime) -> List[Tuple[datetime, datetime, str]]:
        """Generate demo segments for testing."""
        statuses = ["running", "shutdown", "stop", "maintenance", "alarm"]
        segments = []
        current = start_time
        while current < end_time:
            status = random.choice(statuses)
            duration = timedelta(minutes=random.randint(30, 180))
            seg_end = min(current + duration, end_time)
            segments.append((current, seg_end, status))
            current = seg_end
        return segments

    def emit_device_statuses(self, statuses: Dict[str, Any]) -> None:
        """
        Emit batch device status update.

        Args:
            statuses: Dictionary of code -> DeviceStatusDTO
        """
        try:
            self._signals.device_statuses_updated.emit(statuses)
        except Exception as e:
            logger.error(f"Failed to emit device statuses: {e}")

    def emit_device_status_changed(self, equipment_code: str, status_name: str) -> None:
        """
        Emit single device status change.

        Args:
            equipment_code: Device code
            status_name: New status name
        """
        try:
            self._signals.device_status_changed.emit(equipment_code, status_name)
        except Exception as e:
            logger.error(f"Failed to emit status change: {e}")

    def emit_gantt_data(
        self,
        device_code: str,
        segments: List[Tuple[datetime, datetime, str]],
        start_time: datetime,
        end_time: datetime,
    ) -> None:
        """
        Emit Gantt chart data.

        Args:
            device_code: Device code
            segments: List of (start, end, status) tuples
            start_time: Time range start
            end_time: Time range end
        """
        try:
            self._signals.gantt_data_ready.emit(device_code, segments, start_time, end_time)
        except Exception as e:
            logger.error(f"Failed to emit gantt data: {e}")

    def emit_table_data(
        self,
        device_code: str,
        data_type: str,
        headers: List[str],
        rows: List[Dict[str, Any]],
        status_col: int = -1,
    ) -> None:
        """
        Emit table data for history display.

        Args:
            device_code: Device code
            data_type: Type of data (status, input, output)
            headers: Column headers
            rows: Row data
            status_col: Status column index (-1 if none)
        """
        try:
            data = {
                "device_code": device_code,
                "data_type": data_type,
                "headers": headers,
                "rows": rows,
                "status_col": status_col,
            }
            self._signals.table_data_ready.emit(data)
        except Exception as e:
            logger.error(f"Failed to emit table data: {e}")

    def emit_summary_data(self, records: List[Any]) -> None:
        """
        Emit summary data.

        Args:
            records: Summary records
        """
        try:
            self._signals.summary_data_ready.emit(records)
        except Exception as e:
            logger.error(f"Failed to emit summary data: {e}")

    def emit_sync_started(self) -> None:
        """Emit sync started signal."""
        try:
            self._signals.sync_started.emit()
        except Exception as e:
            logger.error(f"Failed to emit sync started: {e}")

    def emit_sync_completed(self, count: int) -> None:
        """
        Emit sync completed signal.

        Args:
            count: Number of devices synced
        """
        try:
            self._signals.sync_completed.emit(count)
        except Exception as e:
            logger.error(f"Failed to emit sync completed: {e}")

    def emit_error(self, context: str, message: str) -> None:
        """
        Emit error signal.

        Args:
            context: Error context (e.g., "sync", "gantt")
            message: Error message
        """
        try:
            self._signals.error_occurred.emit(context, message)
        except Exception as e:
            logger.error(f"Failed to emit error: {e}")

    @property
    def device_statuses_updated(self):
        """Delegate to signals.device_statuses_updated."""
        return self._signals.device_statuses_updated

    @property
    def device_status_changed(self):
        """Delegate to signals.device_status_changed."""
        return self._signals.device_status_changed

    @property
    def gantt_data_ready(self):
        """Delegate to signals.gantt_data_ready."""
        return self._signals.gantt_data_ready

    @property
    def table_data_ready(self):
        """Delegate to signals.table_data_ready."""
        return self._signals.table_data_ready

    @property
    def summary_data_ready(self):
        """Delegate to signals.summary_data_ready."""
        return self._signals.summary_data_ready

    @property
    def sync_completed(self):
        """Delegate to signals.sync_completed."""
        return self._signals.sync_completed

    @property
    def sync_started(self):
        """Delegate to signals.sync_started."""
        return self._signals.sync_started

    @property
    def error_occurred(self):
        """Delegate to signals.error_occurred."""
        return self._signals.error_occurred

    def clear_cache(self) -> None:
        """Clear any cached data (for cleanup)."""
        self._gantt_provider = None
