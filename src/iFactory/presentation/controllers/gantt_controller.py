"""
Gantt Controller.
Manages Gantt chart data fetching on device click.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot, QThread

from ..state.actions import load_gantt
from ..state.selectors import select_selected_device_id

if TYPE_CHECKING:
    from ..presenters.gantt_presenter import GanttPresenter
    from ..state.store import Store

logger = logging.getLogger(__name__)


STATUS_NAMES = {
    0: "Unknown",
    1: "Running",
    2: "Shutdown",
    3: "Stopped",
    4: "Maintenance",
    5: "Alarm",
}


class GanttFetchThread(QThread):
    """Worker thread for fetching Gantt data using synchronous SQLAlchemy."""

    finished = Signal(str, list)
    error = Signal(str, str)

    def __init__(
        self,
        mssql_url: Optional[str] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._mssql_url = mssql_url
        self._sync_url: Optional[str] = None
        self._device_code: Optional[str] = None
        self._days: int = 1

        if mssql_url:
            self._sync_url = self._convert_to_sync_url(mssql_url)

    def _convert_to_sync_url(self, async_url: str) -> str:
        """Convert async MSSQL URL to sync URL."""
        sync_url = async_url.replace("mssql+aioodbc", "mssql+pyodbc")
        return sync_url

    def set_request(self, device_code: str, days: int = 1) -> None:
        """Set the device to fetch."""
        self._device_code = device_code
        self._days = days

    def run(self) -> None:
        """Run the fetch operation."""
        if not self._device_code or not self._sync_url:
            self.error.emit(
                self._device_code or "unknown",
                "Missing device code or MSSQL URL",
            )
            return

        try:
            segments = self._fetch_sync(self._device_code, self._days)
            logger.info(f"[GanttFetchThread] Fetched {len(segments)} segments " f"for {self._device_code}")
            self.finished.emit(self._device_code, segments)

        except Exception as e:
            logger.error(f"[GanttFetchThread] Error fetching {self._device_code}: {e}")
            self.error.emit(self._device_code, str(e))

    def _fetch_sync(self, device_code: str, days: int) -> List[Dict[str, Any]]:
        """Fetch history using synchronous SQLAlchemy."""
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import NullPool

        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        query = """
        SELECT 
            S.EQUIP_CODE, S.EQUIP_STATUS, S.START_TIME, S.END_TIME, S.REASON_CODE,
            E.EQUIP_NAME
        FROM TT_EQ_STATUS S
        LEFT JOIN TT_EQ_EQUIPMENT E ON S.EQUIP_CODE = E.EQUIP_CODE
        WHERE S.EQUIP_CODE = :code 
            AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
            AND S.START_TIME <= :end_time
            AND (S.END_TIME >= :start_time OR S.END_TIME IS NULL)
        ORDER BY S.START_TIME ASC
        """

        engine = create_engine(self._sync_url, poolclass=NullPool)

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(query),
                    {
                        "code": device_code,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
                rows = result.fetchall()

            segments = []
            for row in rows:
                segment = self._process_row(row, start_time, end_time)
                if segment:
                    segments.append(segment)

            return segments

        finally:
            engine.dispose()

    def _process_row(
        self,
        row: Any,
        window_start: datetime,
        window_end: datetime,
    ) -> Optional[Dict[str, Any]]:
        """Process a database row into a segment dict."""
        try:
            equip_status = int(row[1]) if row[1] else 0
            start_time = self._parse_datetime(row[2])
            end_time = self._parse_datetime(row[3]) if row[3] else window_end

            valid_start = max(start_time, window_start)
            valid_end = min(end_time, window_end)

            if valid_start >= valid_end:
                return None

            duration = (valid_end - valid_start).total_seconds()

            return {
                "start_time": valid_start,
                "end_time": valid_end,
                "status_code": equip_status,
                "status_name": STATUS_NAMES.get(equip_status, "Unknown"),
                "duration_seconds": duration,
            }

        except Exception as e:
            logger.debug(f"[GanttFetchThread] Failed to process row: {e}")
            return None

    def _parse_datetime(self, val: Any) -> datetime:
        """Parse datetime from various formats."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                clean_val = val[:23] if len(val) > 23 else val
                return datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.now()
        return datetime.now()


class GanttController(QObject):
    """
    Controller for Gantt chart operations.
    Fetches data on device click.
    """

    device_gantt_ready = Signal(str, list)
    loading_started = Signal(str)
    loading_finished = Signal(str)
    fetch_error = Signal(str, str)

    CACHE_TTL_SECONDS = 30

    def __init__(
        self,
        device_service,
        presenter: "GanttPresenter",
        store: "Store",
        mssql_url: Optional[str] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._service = device_service
        self._presenter = presenter
        self._store = store
        self._mssql_url = mssql_url

        self._cache: Dict[str, Dict[str, Any]] = {}
        self._pending_devices: set = set()
        self._workers: List[GanttFetchThread] = []
        self._max_workers = 3

        self._store.state_changed.connect(self._on_state_changed)
        self._last_selected_device: Optional[str] = None

        logger.debug("[GanttController] Initialized")

    def set_mssql_url(self, url: str) -> None:
        """Set MSSQL URL for direct fetching."""
        self._mssql_url = url
        logger.info("[GanttController] MSSQL URL configured")

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        """Handle state changes - fetch gantt on device selection."""
        selected_device_id = select_selected_device_id(state)

        if selected_device_id and selected_device_id != self._last_selected_device:
            self._last_selected_device = selected_device_id
            self._fetch_device_gantt(selected_device_id)

    def _fetch_device_gantt(self, device_code: str) -> None:
        """Fetch gantt data for a device using worker thread."""
        if device_code in self._pending_devices:
            return

        if not self._mssql_url:
            logger.warning("[GanttController] No MSSQL URL configured")
            self.fetch_error.emit(device_code, "MSSQL not configured")
            return

        self._pending_devices.add(device_code)
        self.loading_started.emit(device_code)
        logger.info(f"[GanttController] Fetching Gantt data for {device_code}")

        worker = self._get_available_worker()
        worker.set_request(device_code, days=1)
        worker.start()

    def _get_available_worker(self) -> GanttFetchThread:
        """Get an available worker thread or create new one."""
        for worker in self._workers:
            if worker.isFinished():
                return worker

        if len(self._workers) < self._max_workers:
            worker = GanttFetchThread(self._mssql_url, parent=self)
            worker.finished.connect(self._on_worker_finished)
            worker.error.connect(self._on_worker_error)
            self._workers.append(worker)
            return worker

        for worker in self._workers:
            if worker.isRunning():
                worker.wait(100)
                if worker.isFinished():
                    return worker

        return self._workers[0]

    @Slot(str, list)
    def _on_worker_finished(
        self,
        device_code: str,
        segments: List[Dict[str, Any]],
    ) -> None:
        """Handle successful fetch from worker thread."""
        self._pending_devices.discard(device_code)

        self._cache[device_code] = {
            "data": segments,
            "timestamp": datetime.now(),
        }

        self._update_store_with_device_data(device_code, segments)

        self.loading_finished.emit(device_code)
        self.device_gantt_ready.emit(device_code, segments)

        logger.info(f"[GanttController] Gantt ready for {device_code}: {len(segments)} segments")

    @Slot(str, str)
    def _on_worker_error(self, device_code: str, error: str) -> None:
        """Handle error from worker thread."""
        self._pending_devices.discard(device_code)
        self.loading_finished.emit(device_code)
        self.fetch_error.emit(device_code, error)
        logger.error(f"[GanttController] Fetch failed for {device_code}: {error}")

    def _update_store_with_device_data(
        self,
        device_code: str,
        segments: List[Dict[str, Any]],
    ) -> None:
        """Update store with new gantt data."""
        state = self._store.get_state()
        current_gantt = dict(state.get("gantt_data", {}))
        current_gantt[device_code] = segments
        self._store.dispatch(load_gantt(current_gantt))

    def get_cached_segments(self, device_code: str) -> List[Dict[str, Any]]:
        """Get cached segments for a device."""
        cached = self._cache.get(device_code)
        if cached:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                return cached.get("data", [])
        return []

    def load_device_gantt(self, device_code: str, device_name: str = "") -> None:
        """Public method to load device gantt."""
        self._fetch_device_gantt(device_code)

    def shutdown(self) -> None:
        """Clean shutdown of controller."""
        for worker in self._workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)

        self._workers.clear()
        self._cache.clear()

        logger.info("[GanttController] Shutdown complete")


__all__ = ["GanttController", "GanttFetchThread"]
