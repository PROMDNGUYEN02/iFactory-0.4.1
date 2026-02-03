# File: presentation/viewmodels/gantt_viewmodel.py
"""
Gantt Chart ViewModel - Optimized to prevent duplicate emissions.

FIXED: Single emission per chart ready event.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtCore import QThread, Signal, Slot, QMutex, QMutexLocker

from .base import AsyncViewModelMixin, BaseViewModel, UiState
from .models.gantt_model import (
    GanttChartModel,
    GanttHourMarkModel,
    GanttSegmentModel,
    GanttStatsModel,
    GanttLoadingState,
    STATUS_GRADIENTS,
    STATUS_NAMES,
)
from ..constants.status import Status

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class GanttFetchWorker(QThread):
    """
    Worker thread for fetching Gantt data using synchronous SQLAlchemy.
    Thread-safe with proper connection cleanup.
    """

    finished = Signal(str, list)
    error = Signal(str, str)

    def __init__(self, mssql_url: Optional[str] = None, parent=None):
        super().__init__(parent)
        self._mssql_url = mssql_url
        self._sync_url: Optional[str] = None
        self._device_code: Optional[str] = None
        self._days: int = 1
        self._is_cancelled: bool = False
        self._mutex = QMutex()

        if mssql_url:
            self._sync_url = self._convert_to_sync_url(mssql_url)

    def _convert_to_sync_url(self, async_url: str) -> str:
        return async_url.replace("mssql+aioodbc", "mssql+pyodbc")

    def set_request(self, device_code: str, days: int = 1) -> None:
        with QMutexLocker(self._mutex):
            self._device_code = device_code
            self._days = days
            self._is_cancelled = False

    def cancel(self) -> None:
        with QMutexLocker(self._mutex):
            self._is_cancelled = True

    def run(self) -> None:
        with QMutexLocker(self._mutex):
            if self._is_cancelled:
                return
            device_code = self._device_code
            days = self._days
            sync_url = self._sync_url

        if not device_code or not sync_url:
            self.error.emit(device_code or "unknown", "Missing device code or MSSQL URL")
            return

        try:
            segments = self._fetch_sync(device_code, days, sync_url)

            with QMutexLocker(self._mutex):
                if self._is_cancelled:
                    return

            logger.info(f"[GanttFetchWorker] Fetched {len(segments)} segments for {device_code}")
            self.finished.emit(device_code, segments)

        except Exception as e:
            logger.error(f"[GanttFetchWorker] Error: {e}")
            self.error.emit(device_code, str(e))

    def _fetch_sync(self, device_code: str, days: int, sync_url: str) -> List[Dict[str, Any]]:
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

        engine = create_engine(sync_url, poolclass=NullPool)
        segments = []

        try:
            with engine.connect() as conn:
                result = conn.execute(
                    text(query),
                    {"code": device_code, "start_time": start_time, "end_time": end_time},
                )
                rows = result.fetchall()

            for row in rows:
                segment = self._process_row(row, start_time, end_time)
                if segment:
                    segments.append(segment)

        finally:
            engine.dispose()

        return segments

    def _process_row(self, row: Any, window_start: datetime, window_end: datetime) -> Optional[Dict[str, Any]]:
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
            logger.debug(f"[GanttFetchWorker] Failed to process row: {e}")
            return None

    def _parse_datetime(self, val: Any) -> datetime:
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


class GanttChartViewModel(BaseViewModel, AsyncViewModelMixin):
    """
    ViewModel for Gantt Chart.

    FIXED: Single chartReady emission per fetch.
    """

    chartReady = Signal(object)
    loadingStateChanged = Signal(object)

    CACHE_TTL_SECONDS = 30
    MAX_WORKERS = 3

    def __init__(self, mssql_url: Optional[str] = None, parent=None):
        BaseViewModel.__init__(self, parent)
        AsyncViewModelMixin.__init__(self)

        self._mssql_url = mssql_url
        self._current_chart: Optional[GanttChartModel] = None
        self._current_device: Optional[str] = None
        self._loading_state = GanttLoadingState(device_code="")
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._workers: List[GanttFetchWorker] = []
        self._pending_devices: set = set()

        # Track emitted charts to prevent duplicates
        self._last_emitted_chart_id: str = ""

    def initialize(self) -> None:
        self._set_state(UiState.idle())
        logger.info("[GanttChartViewModel] Initialized")

    def set_mssql_url(self, url: str) -> None:
        self._mssql_url = url
        logger.info("[GanttChartViewModel] MSSQL URL configured")

    @property
    def current_chart(self) -> Optional[GanttChartModel]:
        return self._current_chart

    @property
    def current_device(self) -> Optional[str]:
        return self._current_device

    @property
    def loading_state(self) -> GanttLoadingState:
        return self._loading_state

    def load_device_chart(self, device_code: str, device_name: str = "", days: int = 1) -> None:
        if self._is_disposed:
            return

        if device_code in self._pending_devices:
            logger.debug(f"[GanttChartViewModel] Already loading {device_code}")
            return

        cached = self._get_from_cache(device_code)
        if cached:
            logger.debug(f"[GanttChartViewModel] Using cached data for {device_code}")
            self._process_segments(device_code, device_name or device_code, cached)
            return

        if not self._mssql_url:
            self._set_loading_state(device_code, error="MSSQL not configured")
            return

        self._current_device = device_code
        self._pending_devices.add(device_code)
        self._set_loading_state(device_code, is_loading=True)
        self._set_loading(True, f"Loading chart for {device_code}...")

        logger.info(f"[GanttChartViewModel] Loading chart for {device_code}")

        worker = self._get_available_worker()
        worker.set_request(device_code, days)
        worker.start()

    def clear_chart(self) -> None:
        self._current_chart = None
        self._current_device = None
        self._last_emitted_chart_id = ""
        self._set_state(UiState.idle())

    def get_cached_segments(self, device_code: str) -> List[Dict[str, Any]]:
        cached = self._cache.get(device_code)
        if cached:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                return cached.get("data", [])
        return []

    def _get_from_cache(self, device_code: str) -> Optional[List[Dict[str, Any]]]:
        cached = self._cache.get(device_code)
        if cached:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                return cached.get("data")
        return None

    def _get_available_worker(self) -> GanttFetchWorker:
        for worker in self._workers:
            if worker.isFinished():
                return worker

        if len(self._workers) < self.MAX_WORKERS:
            worker = GanttFetchWorker(self._mssql_url, parent=self)
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
    def _on_worker_finished(self, device_code: str, segments: List[Dict[str, Any]]) -> None:
        self._pending_devices.discard(device_code)
        self._cache[device_code] = {"data": segments, "timestamp": datetime.now()}
        self._process_segments(device_code, device_code, segments)

    @Slot(str, str)
    def _on_worker_error(self, device_code: str, error: str) -> None:
        self._pending_devices.discard(device_code)
        self._set_loading_state(device_code, error=error)
        self._set_error(f"Failed to load chart: {error}")
        logger.error(f"[GanttChartViewModel] Fetch failed: {device_code}: {error}")

    def _process_segments(self, device_code: str, device_name: str, raw_segments: List[Dict[str, Any]]) -> None:
        now = datetime.now()
        end = now
        start = end - timedelta(hours=24)
        total_seconds = max((end - start).total_seconds(), 1)

        segments = self._create_segment_models(raw_segments, start, end, total_seconds)
        hour_marks = self._generate_hour_marks(start, end, total_seconds)
        stats = self._calculate_stats(segments, total_seconds)
        current_status, current_color = self._get_current_status(segments, now)

        chart = GanttChartModel(
            device_code=device_code,
            device_name=device_name or device_code,
            segments=segments,
            hour_marks=hour_marks,
            start_time=start,
            end_time=end,
            total_duration_seconds=total_seconds,
            stats=stats,
            current_status=current_status,
            current_status_color=current_color,
        )

        # Generate chart ID for duplicate detection
        chart_id = f"{device_code}:{len(segments)}"

        # Skip if same as last emitted
        if chart_id == self._last_emitted_chart_id:
            logger.debug(f"[GanttChartViewModel] Skipping duplicate emission for {device_code}")
            return

        self._last_emitted_chart_id = chart_id
        self._current_chart = chart
        self._set_loading_state(device_code, is_loading=False)
        self._set_success(data=chart)

        # Log and emit ONCE
        logger.info(f"[GanttChartViewModel] Chart ready: {device_code}, {len(segments)} segments")
        self.chartReady.emit(chart)

    def _create_segment_models(
        self, raw_segments: List[Dict[str, Any]], start: datetime, end: datetime, total_seconds: float
    ) -> List[GanttSegmentModel]:
        now = datetime.now()
        segments: List[GanttSegmentModel] = []

        for seg in raw_segments:
            seg_start = seg.get("start_time")
            seg_end = seg.get("end_time")
            status_code = seg.get("status_code", 0)

            if not seg_start or not seg_end:
                continue

            if seg_end < start or seg_start > end:
                continue

            clipped_start = max(seg_start, start)
            clipped_end = min(seg_end, end)

            duration = (clipped_end - clipped_start).total_seconds()
            if duration <= 0:
                continue

            width_percent = duration / total_seconds
            gradient = STATUS_GRADIENTS.get(status_code, STATUS_GRADIENTS[0])
            is_current = clipped_start <= now <= clipped_end

            model = GanttSegmentModel(
                start_time=clipped_start,
                end_time=clipped_end,
                status_code=status_code,
                status_name=Status.get_name(status_code),
                status_color=Status.get_color(status_code),
                duration_seconds=duration,
                duration_display=self._format_duration(duration),
                width_percent=width_percent,
                gradient_start=gradient[0],
                gradient_end=gradient[1],
                is_current=is_current,
            )
            segments.append(model)

        return segments

    def _generate_hour_marks(self, start: datetime, end: datetime, total_seconds: float) -> List[GanttHourMarkModel]:
        marks: List[GanttHourMarkModel] = []

        current = start.replace(minute=0, second=0, microsecond=0)
        if current < start:
            current += timedelta(hours=1)

        while current <= end:
            offset_seconds = (current - start).total_seconds()
            x_percent = offset_seconds / total_seconds

            hour = current.hour
            is_major = hour % 6 == 0
            label = current.strftime("%H:%M") if is_major else current.strftime("%H")

            marks.append(
                GanttHourMarkModel(
                    hour=hour,
                    x_percent=x_percent,
                    is_major=is_major,
                    label=label,
                )
            )

            current += timedelta(hours=1)

        return marks

    def _calculate_stats(self, segments: List[GanttSegmentModel], total_seconds: float) -> GanttStatsModel:
        running = stopped = alarm = maintenance = shutdown = 0.0

        for seg in segments:
            duration = seg.duration_seconds
            if seg.status_code == 1:
                running += duration
            elif seg.status_code == 2:
                shutdown += duration
            elif seg.status_code == 3:
                stopped += duration
            elif seg.status_code == 4:
                maintenance += duration
            elif seg.status_code == 5:
                alarm += duration

        running_pct = (running / total_seconds * 100) if total_seconds > 0 else 0
        stopped_pct = (stopped / total_seconds * 100) if total_seconds > 0 else 0
        alarm_pct = (alarm / total_seconds * 100) if total_seconds > 0 else 0

        available = total_seconds - shutdown - maintenance
        oee = (running / available * 100) if available > 0 else 0

        return GanttStatsModel(
            total_running_seconds=running,
            total_stopped_seconds=stopped,
            total_alarm_seconds=alarm,
            total_maintenance_seconds=maintenance,
            total_shutdown_seconds=shutdown,
            running_percent=running_pct,
            stopped_percent=stopped_pct,
            alarm_percent=alarm_pct,
            oee_estimate=oee,
        )

    def _get_current_status(self, segments: List[GanttSegmentModel], now: datetime) -> Tuple[str, str]:
        for seg in reversed(segments):
            if seg.is_current or seg.end_time >= now:
                return seg.status_name, seg.status_color

        if segments:
            last = segments[-1]
            return last.status_name, last.status_color

        return "Unknown", "Transparent"

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def _set_loading_state(self, device_code: str, is_loading: bool = False, error: str = "") -> None:
        self._loading_state = GanttLoadingState(
            device_code=device_code,
            is_loading=is_loading,
            error_message=error,
        )
        self.loadingStateChanged.emit(self._loading_state)

    def dispose(self) -> None:
        if self._is_disposed:
            return

        for worker in self._workers:
            worker.cancel()
            if worker.isRunning():
                worker.quit()
                worker.wait(500)

        self._workers.clear()
        self._cache.clear()
        self._pending_devices.clear()

        super().dispose()
        logger.info("[GanttChartViewModel] Disposed")


__all__ = ["GanttChartViewModel", "GanttFetchWorker"]
