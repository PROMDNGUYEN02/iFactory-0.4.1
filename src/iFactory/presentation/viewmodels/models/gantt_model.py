"""
Gantt Chart Data Models.

Pure data classes for Gantt chart information.
These are immutable data containers used by ViewModels.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Tuple


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
    """Complete Gantt chart data for a device."""

    device_code: str
    device_name: str
    segments: List[GanttSegmentModel]
    hour_marks: List[GanttHourMarkModel]
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float
    stats: GanttStatsModel = field(default_factory=GanttStatsModel)
    current_status: str = "Unknown"
    current_status_color: str = "#64748B"

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def time_range_display(self) -> str:
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"

    @property
    def date_display(self) -> str:
        return self.start_time.strftime("%B %d, %Y")

    @staticmethod
    def empty(device_code: str) -> "GanttChartModel":
        now = datetime.now()
        return GanttChartModel(
            device_code=device_code,
            device_name=device_code,
            segments=[],
            hour_marks=[],
            start_time=now,
            end_time=now,
            total_duration_seconds=0,
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
    0: ("#94A3B8", "#64748B"),  # Unknown - Slate
    1: ("#34D399", "#059669"),  # Running - Emerald
    2: ("#60A5FA", "#3B82F6"),  # Shutdown - Blue
    3: ("#FBBF24", "#D97706"),  # Stopped - Amber
    4: ("#A78BFA", "#7C3AED"),  # Maintenance - Violet
    5: ("#F87171", "#DC2626"),  # Alarm - Red
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
