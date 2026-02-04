# src/iFactory/presentation/viewmodels/gantt_viewmodel.py
"""
Gantt Chart ViewModel - Enhanced with better error handling and metrics.

Features:
- ID mapping support for display vs remote device IDs
- Fixed NULL end_time handling for zombie rows
- Worker pool with proper lifecycle
- Performance metrics tracking
- Cache with configurable TTL
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple, Protocol

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


# ============================================================================
# Protocols
# ============================================================================


class IDeviceIdMapper(Protocol):
    """Protocol for device ID mapping (display <-> remote)."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        """Convert display IDs to remote IDs."""
        ...

    def to_display_id(self, remote_id: str) -> str:
        """Convert remote ID to display ID."""
        ...

    def to_remote_id(self, display_id: str) -> str:
        """Convert display ID to remote ID."""
        ...


class NoOpIdMapper:
    """Default mapper that returns IDs unchanged."""

    def to_remote_ids(self, display_ids: List[str]) -> List[str]:
        return display_ids

    def to_display_id(self, remote_id: str) -> str:
        return remote_id

    def to_remote_id(self, display_id: str) -> str:
        return display_id


# ============================================================================
# Metrics
# ============================================================================


@dataclass
class GanttMetrics:
    """Metrics for Gantt chart operations."""

    total_fetches: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    errors: int = 0
    total_fetch_time_ms: float = 0.0

    @property
    def cache_hit_rate(self) -> float:
        total = self.cache_hits + self.cache_misses
        return (self.cache_hits / total * 100) if total > 0 else 0.0

    @property
    def avg_fetch_time_ms(self) -> float:
        fetches = self.cache_misses  # Only count actual DB fetches
        return (self.total_fetch_time_ms / fetches) if fetches > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_fetches": self.total_fetches,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "errors": self.errors,
            "cache_hit_rate": f"{self.cache_hit_rate:.1f}%",
            "avg_fetch_time_ms": f"{self.avg_fetch_time_ms:.1f}ms",
        }


# ============================================================================
# Worker Thread
# ============================================================================


class GanttFetchWorker(QThread):
    """
    Worker thread for fetching Gantt data.

    Features:
    - Excludes old "zombie" rows with NULL end_time
    - Only allows NULL end_time for segments that started today
    - Supports ID mapping for display vs remote device IDs
    - Performance timing
    """

    finished = Signal(str, str, list, datetime, datetime, float)  # Added: fetch_time_ms
    error = Signal(str, str)

    def __init__(
        self,
        mssql_url: Optional[str] = None,
        id_mapper: Optional[IDeviceIdMapper] = None,
        parent=None,
    ):
        super().__init__(parent)
        self._mssql_url = mssql_url
        self._id_mapper = id_mapper or NoOpIdMapper()
        self._sync_url: Optional[str] = None
        self._device_code: Optional[str] = None  # Display code
        self._is_cancelled: bool = False
        self._mutex = QMutex()

        if mssql_url:
            self._sync_url = self._convert_to_sync_url(mssql_url)

    def _convert_to_sync_url(self, async_url: str) -> str:
        return async_url.replace("mssql+aioodbc", "mssql+pyodbc")

    def set_id_mapper(self, mapper: IDeviceIdMapper) -> None:
        """Set ID mapper for display <-> remote ID conversion."""
        with QMutexLocker(self._mutex):
            self._id_mapper = mapper or NoOpIdMapper()

    def set_request(self, device_code: str) -> None:
        """Set device code to fetch (display ID)."""
        with QMutexLocker(self._mutex):
            self._device_code = device_code
            self._is_cancelled = False

    def cancel(self) -> None:
        with QMutexLocker(self._mutex):
            self._is_cancelled = True

    def run(self) -> None:
        start_time = datetime.now()

        with QMutexLocker(self._mutex):
            if self._is_cancelled:
                return
            display_code = self._device_code
            sync_url = self._sync_url
            id_mapper = self._id_mapper

        if not display_code or not sync_url:
            self.error.emit(display_code or "unknown", "Missing device code or MSSQL URL")
            return

        try:
            now = datetime.now()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

            # Convert display ID to remote ID for database query
            remote_code = id_mapper.to_remote_id(display_code)

            if remote_code != display_code:
                logger.debug(f"[GanttFetchWorker] ID mapping: {display_code} -> {remote_code}")

            segments = self._fetch_sync(remote_code, start_of_day, now, sync_url)

            with QMutexLocker(self._mutex):
                if self._is_cancelled:
                    return

            fetch_time_ms = (datetime.now() - start_time).total_seconds() * 1000
            logger.info(f"[GanttFetchWorker] Fetched {len(segments)} segments for {display_code} in {fetch_time_ms:.0f}ms")

            self.finished.emit(display_code, remote_code, segments, start_of_day, now, fetch_time_ms)

        except Exception as e:
            logger.error(f"[GanttFetchWorker] Error: {e}")
            self.error.emit(display_code, str(e))

    def _fetch_sync(
        self,
        device_code: str,  # Remote code for DB query
        start_time: datetime,
        end_time: datetime,
        sync_url: str,
    ) -> List[Dict[str, Any]]:
        from sqlalchemy import create_engine, text
        from sqlalchemy.pool import NullPool

        # FIXED QUERY: Properly handle NULL end_time
        query = """
        SELECT 
            S.EQUIP_CODE, 
            S.EQUIP_STATUS, 
            S.START_TIME, 
            S.END_TIME, 
            S.REASON_CODE,
            E.EQUIP_NAME
        FROM TT_EQ_STATUS S
        LEFT JOIN TT_EQ_EQUIPMENT E ON S.EQUIP_CODE = E.EQUIP_CODE
        WHERE S.EQUIP_CODE = :code 
            AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
            AND (
                -- Closed segments: must overlap with window
                (S.END_TIME IS NOT NULL 
                    AND S.START_TIME <= :end_time 
                    AND S.END_TIME >= :start_time)
                OR
                -- Open segments (NULL end_time): only if started today
                (S.END_TIME IS NULL AND S.START_TIME >= :start_time)
            )
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

            total_duration = sum(s.get("duration_seconds", 0) for s in segments)
            logger.debug(f"[GanttFetchWorker] {device_code}: {len(segments)} segments, " f"total={total_duration/3600:.1f}h")

        finally:
            engine.dispose()

        return segments

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

            # Handle NULL end_time (ongoing status)
            if row[3]:
                end_time = self._parse_datetime(row[3])
            else:
                end_time = window_end

            # Clip to window
            valid_start = max(start_time, window_start)
            valid_end = min(end_time, window_end)

            if valid_start >= valid_end:
                return None

            duration_seconds = (valid_end - valid_start).total_seconds()

            # Sanity check
            if duration_seconds > 86400:
                logger.warning(
                    f"[GanttFetchWorker] Segment duration {duration_seconds/3600:.1f}h > 24h, " f"clipping. Start={valid_start}, End={valid_end}"
                )
                duration_seconds = min(duration_seconds, 86400)

            return {
                "start_time": valid_start,
                "end_time": valid_end,
                "status_code": equip_status,
                "status_name": STATUS_NAMES.get(equip_status, "Unknown"),
                "duration_seconds": duration_seconds,
            }
        except Exception as e:
            logger.debug(f"[GanttFetchWorker] Failed to process row: {e}")
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


# ============================================================================
# ViewModel
# ============================================================================


class GanttChartViewModel(BaseViewModel, AsyncViewModelMixin):
    """
    ViewModel for Gantt Chart.

    Display: 00:00 - 24:00 of current day
    Data: 00:00 - now
    Future: now - 24:00 (striped zone)

    Features:
    - ID mapping support for display vs remote device IDs
    - Worker pool with proper lifecycle
    - Caching with TTL
    - Performance metrics
    """

    # Signals
    chartReady = Signal(object)
    loadingStateChanged = Signal(object)
    metricsUpdated = Signal(dict)

    # Configuration
    CACHE_TTL_SECONDS = 30
    MAX_WORKERS = 3

    def __init__(
        self,
        mssql_url: Optional[str] = None,
        id_mapper: Optional[IDeviceIdMapper] = None,
        parent=None,
    ):
        BaseViewModel.__init__(self, parent)
        AsyncViewModelMixin.__init__(self)

        self._mssql_url = mssql_url
        self._id_mapper = id_mapper or NoOpIdMapper()
        self._current_chart: Optional[GanttChartModel] = None
        self._current_device: Optional[str] = None
        self._loading_state = GanttLoadingState(device_code="")

        # Cache keyed by DISPLAY code
        self._cache: Dict[str, Dict[str, Any]] = {}

        # Worker pool
        self._workers: List[GanttFetchWorker] = []
        self._pending_devices: set = set()

        # Deduplication
        self._last_emitted_chart_id: str = ""

        # Metrics
        self._metrics = GanttMetrics()

    def initialize(self) -> None:
        self._set_state(UiState.idle())
        logger.info("[GanttChartViewModel] Initialized")

    # ========================================================================
    # Configuration
    # ========================================================================

    def set_mssql_url(self, url: str) -> None:
        self._mssql_url = url
        logger.info("[GanttChartViewModel] MSSQL URL configured")

    def set_id_mapper(self, mapper: IDeviceIdMapper) -> None:
        """Set ID mapper for display <-> remote ID conversion."""
        self._id_mapper = mapper or NoOpIdMapper()
        # Update existing workers
        for worker in self._workers:
            worker.set_id_mapper(self._id_mapper)
        logger.info("[GanttChartViewModel] ID mapper configured")

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def current_chart(self) -> Optional[GanttChartModel]:
        return self._current_chart

    @property
    def current_device(self) -> Optional[str]:
        return self._current_device

    @property
    def loading_state(self) -> GanttLoadingState:
        return self._loading_state

    @property
    def metrics(self) -> GanttMetrics:
        return self._metrics

    # ========================================================================
    # Public API
    # ========================================================================

    def load_device_chart(self, device_code: str, device_name: str = "") -> None:
        """
        Load Gantt chart for a device.

        Args:
            device_code: Display ID (e.g., "ALS01")
            device_name: Optional display name
        """
        if self._is_disposed:
            return

        self._metrics.total_fetches += 1

        if device_code in self._pending_devices:
            logger.debug(f"[GanttChartViewModel] Already loading {device_code}")
            return

        # Check cache first
        cached = self._get_from_cache(device_code)
        if cached:
            self._metrics.cache_hits += 1
            logger.debug(f"[GanttChartViewModel] Cache hit for {device_code}")
            now = datetime.now()
            start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
            self._process_segments(device_code, device_name or device_code, cached, start_of_day, now)
            return

        self._metrics.cache_misses += 1

        if not self._mssql_url:
            self._set_loading_state(device_code, error="MSSQL not configured")
            return

        self._current_device = device_code
        self._pending_devices.add(device_code)
        self._set_loading_state(device_code, is_loading=True)
        self._set_loading(True, f"Loading chart for {device_code}...")

        logger.info(f"[GanttChartViewModel] Loading chart for {device_code}")

        worker = self._get_available_worker()
        worker.set_request(device_code)
        worker.start()

    def clear_chart(self) -> None:
        """Clear current chart."""
        self._current_chart = None
        self._current_device = None
        self._last_emitted_chart_id = ""
        self._set_state(UiState.idle())

    def get_cached_segments(self, device_code: str) -> List[Dict[str, Any]]:
        """Get cached segments for a device (by display code)."""
        cached = self._cache.get(device_code)
        if cached:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                return cached.get("data", [])
        return []

    def invalidate_cache(self, device_code: Optional[str] = None) -> None:
        """Invalidate cache for device or all devices."""
        if device_code:
            self._cache.pop(device_code, None)
        else:
            self._cache.clear()

    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary."""
        return self._metrics.to_dict()

    # ========================================================================
    # Cache Management
    # ========================================================================

    def _get_from_cache(self, device_code: str) -> Optional[List[Dict[str, Any]]]:
        """Get from cache by display code."""
        cached = self._cache.get(device_code)
        if cached:
            age = (datetime.now() - cached.get("timestamp", datetime.min)).total_seconds()
            if age < self.CACHE_TTL_SECONDS:
                return cached.get("data")
        return None

    # ========================================================================
    # Worker Management
    # ========================================================================

    def _get_available_worker(self) -> GanttFetchWorker:
        """Get or create an available worker."""
        # Find finished worker
        for worker in self._workers:
            if worker.isFinished():
                return worker

        # Create new if under limit
        if len(self._workers) < self.MAX_WORKERS:
            worker = GanttFetchWorker(
                self._mssql_url,
                id_mapper=self._id_mapper,
                parent=self,
            )
            worker.finished.connect(self._on_worker_finished)
            worker.error.connect(self._on_worker_error)
            self._workers.append(worker)
            return worker

        # Wait for any worker
        for worker in self._workers:
            if worker.isRunning():
                worker.wait(100)
                if worker.isFinished():
                    return worker

        return self._workers[0]

    @Slot(str, str, list, datetime, datetime, float)
    def _on_worker_finished(
        self,
        display_code: str,
        remote_code: str,
        segments: List[Dict[str, Any]],
        fetch_start: datetime,
        fetch_end: datetime,
        fetch_time_ms: float,
    ) -> None:
        """Handle worker completion."""
        self._pending_devices.discard(display_code)
        self._metrics.total_fetch_time_ms += fetch_time_ms

        # Cache by DISPLAY code
        self._cache[display_code] = {
            "data": segments,
            "timestamp": datetime.now(),
        }

        # Process with DISPLAY code
        self._process_segments(display_code, display_code, segments, fetch_start, fetch_end)

    @Slot(str, str)
    def _on_worker_error(self, device_code: str, error: str) -> None:
        """Handle worker error."""
        self._pending_devices.discard(device_code)
        self._metrics.errors += 1
        self._set_loading_state(device_code, error=error)
        self._set_error(f"Failed to load chart: {error}")
        logger.error(f"[GanttChartViewModel] Fetch failed: {device_code}: {error}")

    # ========================================================================
    # Data Processing
    # ========================================================================

    def _process_segments(
        self,
        device_code: str,
        device_name: str,
        raw_segments: List[Dict[str, Any]],
        fetch_start: datetime,
        fetch_end: datetime,
    ) -> None:
        """Process segments for display."""
        now = datetime.now()

        display_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        display_end = display_start + timedelta(days=1)
        total_seconds = (display_end - display_start).total_seconds()

        segments = self._create_segment_models(raw_segments, display_start, fetch_end, total_seconds)
        hour_marks = self._generate_hour_marks(display_start, display_end, total_seconds)

        actual_seconds = (fetch_end - display_start).total_seconds()
        stats = self._calculate_stats(segments, actual_seconds)

        current_status, current_color = self._get_current_status(segments, now)

        chart = GanttChartModel(
            device_code=device_code,
            device_name=device_name or device_code,
            segments=segments,
            hour_marks=hour_marks,
            start_time=display_start,
            end_time=display_end,
            current_time=now,
            total_duration_seconds=total_seconds,
            stats=stats,
            current_status=current_status,
            current_status_color=current_color,
        )

        # Deduplication
        chart_id = f"{device_code}:{len(segments)}"
        if chart_id == self._last_emitted_chart_id:
            logger.debug(f"[GanttChartViewModel] Skipping duplicate emission for {device_code}")
            return

        self._last_emitted_chart_id = chart_id
        self._current_chart = chart
        self._set_loading_state(device_code, is_loading=False)
        self._set_success(data=chart)

        logger.info(
            f"[GanttChartViewModel] Chart ready: {device_code}, {len(segments)} segments, "
            f"RUN={stats.total_running_seconds/3600:.1f}h ({stats.running_percent:.1f}%), "
            f"STOP={stats.total_stopped_seconds/3600:.1f}h"
        )
        self.chartReady.emit(chart)
        self.metricsUpdated.emit(self._metrics.to_dict())

    def _create_segment_models(
        self,
        raw_segments: List[Dict[str, Any]],
        start: datetime,
        end: datetime,
        total_seconds: float,
    ) -> List[GanttSegmentModel]:
        """Create segment models from raw data."""
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

    def _generate_hour_marks(
        self,
        start: datetime,
        end: datetime,
        total_seconds: float,
    ) -> List[GanttHourMarkModel]:
        """Generate hour marks for 00:00 - 24:00."""
        marks: List[GanttHourMarkModel] = []
        current = start

        while current <= end:
            offset_seconds = (current - start).total_seconds()
            x_percent = offset_seconds / total_seconds

            hour = current.hour
            is_major = hour % 6 == 0

            if hour == 0 and current == start:
                label = "00:00"
            elif current == end:
                label = "24:00"
            elif is_major:
                label = current.strftime("%H:%M")
            else:
                label = current.strftime("%H")

            marks.append(
                GanttHourMarkModel(
                    hour=hour if current != end else 24,
                    x_percent=x_percent,
                    is_major=is_major,
                    label=label,
                )
            )

            current += timedelta(hours=1)

        return marks

    def _calculate_stats(
        self,
        segments: List[GanttSegmentModel],
        total_seconds: float,
    ) -> GanttStatsModel:
        """Calculate statistics from segments."""
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

        day_seconds = 86400.0
        running_pct = (running / day_seconds * 100) if day_seconds > 0 else 0
        stopped_pct = (stopped / day_seconds * 100) if day_seconds > 0 else 0
        alarm_pct = (alarm / day_seconds * 100) if day_seconds > 0 else 0

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

    def _get_current_status(
        self,
        segments: List[GanttSegmentModel],
        now: datetime,
    ) -> Tuple[str, str]:
        """Get current status from segments."""
        for seg in reversed(segments):
            if seg.is_current or seg.end_time >= now:
                return seg.status_name, seg.status_color

        if segments:
            last = segments[-1]
            return last.status_name, last.status_color

        return "Unknown", "Transparent"

    def _format_duration(self, seconds: float) -> str:
        """Format duration for display."""
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"

    def _set_loading_state(
        self,
        device_code: str,
        is_loading: bool = False,
        error: str = "",
    ) -> None:
        """Update loading state."""
        self._loading_state = GanttLoadingState(
            device_code=device_code,
            is_loading=is_loading,
            error_message=error,
        )
        self.loadingStateChanged.emit(self._loading_state)

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def dispose(self) -> None:
        """Clean up resources."""
        if self._is_disposed:
            return

        # Cancel and cleanup workers
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


__all__ = ["GanttChartViewModel", "GanttFetchWorker", "GanttMetrics"]
