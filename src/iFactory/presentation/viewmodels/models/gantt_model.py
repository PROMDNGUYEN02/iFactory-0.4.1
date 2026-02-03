# File: presentation/viewmodels/models/gantt_model.py
"""
Gantt Chart Data Models - Updated for 00:00-24:00 display.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
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

    NEW: current_time field for rendering future zone.
    """

    device_code: str
    device_name: str
    segments: List[GanttSegmentModel]
    hour_marks: List[GanttHourMarkModel]
    start_time: datetime  # 00:00 today
    end_time: datetime  # 24:00 today (= 00:00 tomorrow)
    total_duration_seconds: float  # Always 86400 (24 hours)
    current_time: Optional[datetime] = None  # NEW: Current time for future zone
    stats: GanttStatsModel = field(default_factory=GanttStatsModel)
    current_status: str = "Unknown"
    current_status_color: str = "Transparent"

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


# Need import for empty() method
from datetime import timedelta

# Color palette with gradients for status visualization
STATUS_GRADIENTS: dict[int, Tuple[str, str]] = {
    0: ("Transparent", "Transparent"),
    1: ("#2ECC71", "#2ECC71"),
    2: ("#7F8C8D", "#7F8C8D"),
    3: ("#E74C3C", "#E74C3C"),
    4: ("#9B59B6", "#9B59B6"),
    5: ("#F1C40F", "#F1C40F"),
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
