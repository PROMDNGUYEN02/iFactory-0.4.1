# File: presentation/controllers/gantt_controller.py
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


# Status code mapping
STATUS_NAMES = {
    0: "Unknown",
    1: "Running",
    2: "Shutdown",
    3: "Stopped",
    4: "Maintenance",
    5: "Alarm",
}


class GanttFetchThread(QThread):
    """
    Worker thread for fetching Gantt data using SYNCHRONOUS SQLAlchemy.
    Each thread creates its own sync engine to avoid async event loop conflicts.
    """

    finished = Signal(str, list)  # device_code, segments
    error = Signal(str, str)  # device_code, error_message

    def __init__(self, mssql_url: Optional[str] = None, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._mssql_url = mssql_url
        self._sync_url: Optional[str] = None
        self._device_code: Optional[str] = None
        self._days: int = 1

        # Convert async URL to sync URL
        if mssql_url:
            self._sync_url = self._convert_to_sync_url(mssql_url)

    def _convert_to_sync_url(self, async_url: str) -> str:
        """Convert async MSSQL URL to sync URL."""
        # mssql+aioodbc://... -> mssql+pyodbc://...
        sync_url = async_url.replace("mssql+aioodbc", "mssql+pyodbc")
        # Remove async-specific params if any
        return sync_url

    def set_request(self, device_code: str, days: int = 1) -> None:
        """Set the device to fetch."""
        self._device_code = device_code
        self._days = days

    def run(self) -> None:
        """Run the fetch operation in this thread."""
        if not self._device_code or not self._sync_url:
            self.error.emit(self._device_code or "unknown", "Missing device code or MSSQL URL")
            return

        try:
            segments = self._fetch_sync(self._device_code, self._days)
            logger.info(f"[GanttFetchThread] Fetched {len(segments)} segments for {self._device_code}")
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

        # Create sync engine with NullPool (no connection pooling)
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

            logger.info(f"[GanttFetchThread] SQL returned {len(rows)} rows for {device_code}")

            # Process rows into segments
            segments = []
            for row in rows:
                segment = self._process_row(row, start_time, end_time)
                if segment:
                    segments.append(segment)

            return segments

        finally:
            engine.dispose()

    def _process_row(self, row: Any, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
        """Process a database row into a segment dict."""
        try:
            # Parse row data
            equip_code = str(row[0]).strip() if row[0] else "UNKNOWN"
            equip_status = int(row[1]) if row[1] else 0
            start_time = self._parse_datetime(row[2])
            end_time = self._parse_datetime(row[3]) if row[3] else window_end

            # Clip to window
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
    """Controller for Gantt chart operations."""

    # Signals for UI binding
    device_gantt_ready = Signal(str, list)  # device_code, segments
    loading_started = Signal(str)  # device_code
    loading_finished = Signal(str)  # device_code
    fetch_error = Signal(str, str)  # device_code, error

    CACHE_TTL_SECONDS = 30
    BACKGROUND_SYNC_INTERVAL_MS = 30000

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

        # Cache and pending tracking
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._pending_devices: set = set()

        # Worker threads pool (reusable)
        self._workers: List[GanttFetchThread] = []
        self._max_workers = 3

        # Background sync timer
        self._sync_timer = QTimer(self)
        self._sync_timer.setInterval(self.BACKGROUND_SYNC_INTERVAL_MS)
        self._sync_timer.timeout.connect(self._on_background_sync)

        # State tracking
        self._store.state_changed.connect(self._on_state_changed)
        self._last_selected_device: Optional[str] = None

        logger.debug("[GanttController] Initialized")

    def set_mssql_url(self, url: str) -> None:
        """Set MSSQL URL for direct fetching."""
        self._mssql_url = url
        logger.info(f"[GanttController] MSSQL URL configured")

    def start_background_sync(self) -> None:
        if not self._sync_timer.isActive():
            self._sync_timer.start()
            logger.info(f"Gantt background sync started (interval: {self.BACKGROUND_SYNC_INTERVAL_MS}ms)")

    def stop_background_sync(self) -> None:
        self._sync_timer.stop()
        logger.info("Gantt background sync stopped")

    def _on_state_changed(self, state: Dict[str, Any]) -> None:
        """Handle state changes - fetch gantt when device selected."""
        selected_device_id = select_selected_device_id(state)

        if selected_device_id and selected_device_id != self._last_selected_device:
            self._last_selected_device = selected_device_id
            self._fetch_device_gantt(selected_device_id)

    def _fetch_device_gantt(self, device_code: str) -> None:
        """Fetch gantt data for a device using worker thread."""
        if device_code in self._pending_devices:
            logger.debug(f"[GanttController] {device_code} already pending, skipping")
            return

        if not self._mssql_url:
            logger.warning("[GanttController] No MSSQL URL configured")
            self.fetch_error.emit(device_code, "MSSQL not configured")
            return

        self._pending_devices.add(device_code)
        self.loading_started.emit(device_code)
        logger.info(f"[GanttController] Fetching Gantt data for {device_code}")

        # Get or create worker thread
        worker = self._get_available_worker()
        worker.set_request(device_code, days=1)
        worker.start()

    def _get_available_worker(self) -> GanttFetchThread:
        """Get an available worker thread or create new one."""
        # Find finished worker
        for worker in self._workers:
            if worker.isFinished():
                return worker

        # Create new worker if under limit
        if len(self._workers) < self._max_workers:
            worker = GanttFetchThread(self._mssql_url, parent=self)
            worker.finished.connect(self._on_worker_finished)
            worker.error.connect(self._on_worker_error)
            self._workers.append(worker)
            return worker

        # Wait for any worker to finish (shouldn't happen often)
        for worker in self._workers:
            if worker.isRunning():
                worker.wait(100)
                if worker.isFinished():
                    return worker

        # Fallback: return first worker
        return self._workers[0]

    @Slot(str, list)
    def _on_worker_finished(self, device_code: str, segments: List[Dict[str, Any]]) -> None:
        """Handle successful fetch from worker thread."""
        self._pending_devices.discard(device_code)

        # Cache the result
        self._cache[device_code] = {
            "data": segments,
            "timestamp": datetime.now(),
        }

        # Update store
        self._update_store_with_device_data(device_code, segments)

        # Emit signals for UI
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

    def _update_store_with_device_data(self, device_code: str, segments: List[Dict[str, Any]]) -> None:
        """Update store with new gantt data."""
        state = self._store.get_state()
        current_gantt = dict(state.get("gantt_data", {}))
        current_gantt[device_code] = segments
        self._store.dispatch(load_gantt(current_gantt))
        logger.debug(f"[GanttController] Store updated with {len(segments)} segments for {device_code}")

    def _on_background_sync(self) -> None:
        """Background sync using service (async via executor)."""
        if not self._service:
            return

        logger.debug("Running background Gantt sync...")

        # For background sync, we can use the async service since it runs in scheduler
        # This is optional - we might skip background sync for now
        pass

    def get_cached_segments(self, device_code: str) -> List[Dict[str, Any]]:
        """Get cached segments for a device."""
        cached = self._cache.get(device_code)
        if cached:
            return cached.get("data", [])
        return []

    def load_timeline(self, days: int = 1) -> None:
        """Load timeline for visible devices."""
        # Optional: preload data for some devices
        pass

    def load_device_gantt(self, device_code: str, device_name: str = "") -> None:
        """Public method to load device gantt."""
        self._fetch_device_gantt(device_code)

    def shutdown(self) -> None:
        """Clean shutdown of controller."""
        self.stop_background_sync()

        # Stop all workers
        for worker in self._workers:
            if worker.isRunning():
                worker.quit()
                worker.wait(1000)

        self._workers.clear()
        self._cache.clear()

        logger.info("[GanttController] Shutdown complete")


__all__ = ["GanttController", "GanttFetchThread"]
