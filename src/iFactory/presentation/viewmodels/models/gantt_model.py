# File: src/iFactory/presentation/viewmodels/models/gantt_model.py
"""
Gantt Chart Data Models - Updated with live status support.

CHANGES:
- Added live_status_code, live_status_name, live_status_color fields
- Added effective_status properties for UI rendering
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


@dataclass(frozen=True, slots=True)
class GanttSegmentModel:
    """Single segment in the Gantt timeline."""

    start_time: datetime
    end_time: datetime
    status_code: int
    status_name: str
    status_color: str
    duration_seconds: float
    duration_display: str
    width_percent: float
    gradient_start: str = ""
    gradient_end: str = ""
    is_current: bool = False

    @property
    def start_display(self) -> str:
        return self.start_time.strftime("%H:%M:%S")

    @property
    def end_display(self) -> str:
        return self.end_time.strftime("%H:%M:%S")

    @property
    def time_range_display(self) -> str:
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    @property
    def tooltip_text(self) -> str:
        return f"{self.status_name}\n{self.duration_display}\n{self.start_display} - {self.end_display}"


@dataclass(frozen=True, slots=True)
class GanttHourMarkModel:
    """Hour marker for the timeline ruler."""

    hour: int
    x_percent: float
    is_major: bool
    label: str


@dataclass(frozen=True, slots=True)
class GanttStatsModel:
    """Statistics for the Gantt chart."""

    total_running_seconds: float = 0
    total_stopped_seconds: float = 0
    total_alarm_seconds: float = 0
    total_maintenance_seconds: float = 0
    total_shutdown_seconds: float = 0
    running_percent: float = 0
    stopped_percent: float = 0
    alarm_percent: float = 0
    oee_estimate: float = 0

    @property
    def running_display(self) -> str:
        return self._format_duration(self.total_running_seconds)

    @property
    def stopped_display(self) -> str:
        return self._format_duration(self.total_stopped_seconds)

    @property
    def alarm_display(self) -> str:
        return self._format_duration(self.total_alarm_seconds)

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"


@dataclass(frozen=True, slots=True)
class GanttChartModel:
    """
    Complete Gantt chart data for a device.

    UPDATED: Added live status fields for sync with Device Canvas.

    Live status fields:
    - live_status_code: Real-time status from DeviceStatusService
    - live_status_name: Real-time status name
    - live_status_color: Real-time status color

    The UI should use effective_* properties which prioritize live status.
    """

    device_code: str
    device_name: str
    segments: List[GanttSegmentModel]
    hour_marks: List[GanttHourMarkModel]
    start_time: datetime  # 00:00 today
    end_time: datetime  # 24:00 today (= 00:00 tomorrow)
    total_duration_seconds: float  # Always 86400 (24 hours)
    current_time: Optional[datetime] = None  # Current time for future zone
    stats: GanttStatsModel = field(default_factory=GanttStatsModel)

    # Status from segment analysis (fallback)
    current_status: str = "Unknown"
    current_status_color: str = "Transparent"

    # ✅ NEW: Live status from DeviceStatusService (takes priority)
    live_status_code: Optional[int] = None
    live_status_name: Optional[str] = None
    live_status_color: Optional[str] = None

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def time_range_display(self) -> str:
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    @property
    def date_display(self) -> str:
        return self.start_time.strftime("%Y-%m-%d")

    @property
    def future_zone_start(self) -> Optional[datetime]:
        """Start of future zone (from current_time to end_time)."""
        return self.current_time

    @property
    def future_zone_percent(self) -> float:
        """Percentage of the chart that is future time."""
        if not self.current_time or self.total_duration_seconds <= 0:
            return 0.0
        future_seconds = (self.end_time - self.current_time).total_seconds()
        return max(0, future_seconds / self.total_duration_seconds)

    # ========================================================================
    # ✅ NEW: Effective status properties (use live status if available)
    # ========================================================================

    @property
    def has_live_status(self) -> bool:
        """Check if live status is available."""
        return self.live_status_code is not None

    @property
    def effective_status_code(self) -> int:
        """Get effective status code (live if available, otherwise from segments)."""
        if self.live_status_code is not None:
            return self.live_status_code
        # Try to parse from current_status
        status_map = {
            "Running": 1,
            "Shutdown": 2,
            "Stopped": 3,
            "Maintenance": 4,
            "Alarm": 5,
            "Unknown": 0,
        }
        return status_map.get(self.current_status, 0)

    @property
    def effective_status_name(self) -> str:
        """Get effective status name (live if available)."""
        if self.live_status_name:
            return self.live_status_name
        return self.current_status

    @property
    def effective_status_color(self) -> str:
        """Get effective status color (live if available)."""
        if self.live_status_color:
            return self.live_status_color
        return self.current_status_color

    @property
    def is_running(self) -> bool:
        """Check if device is currently running."""
        return self.effective_status_code == 1

    @property
    def is_stopped(self) -> bool:
        """Check if device is currently stopped."""
        return self.effective_status_code == 3

    @property
    def is_alarm(self) -> bool:
        """Check if device is in alarm state."""
        return self.effective_status_code == 5

    @staticmethod
    def empty(device_code: str) -> "GanttChartModel":
        now = datetime.now()
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
        return GanttChartModel(
            device_code=device_code,
            device_name=device_code,
            segments=[],
            hour_marks=[],
            start_time=start,
            end_time=end,
            current_time=now,
            total_duration_seconds=86400,
        )


@dataclass(frozen=True, slots=True)
class GanttLoadingState:
    """State for Gantt loading operations."""

    device_code: str
    is_loading: bool = False
    error_message: str = ""

    @property
    def has_error(self) -> bool:
        return bool(self.error_message)


# Color palette with gradients for status visualization
STATUS_GRADIENTS: dict[int, Tuple[str, str]] = {
    0: ("Transparent", "Transparent"),
    1: ("#2ECC71", "#27AE60"),  # Running - green gradient
    2: ("#7F8C8D", "#707B7C"),  # Shutdown - gray gradient
    3: ("#E74C3C", "#C0392B"),  # Stopped - red gradient
    4: ("#9B59B6", "#8E44AD"),  # Maintenance - purple gradient
    5: ("#F1C40F", "#F39C12"),  # Alarm - yellow/orange gradient
}

STATUS_NAMES: dict[int, str] = {
    0: "Unknown",
    1: "Running",
    2: "Shutdown",
    3: "Stopped",
    4: "Maintenance",
    5: "Alarm",
}


__all__ = [
    "GanttSegmentModel",
    "GanttHourMarkModel",
    "GanttStatsModel",
    "GanttChartModel",
    "GanttLoadingState",
    "STATUS_GRADIENTS",
    "STATUS_NAMES",
]
