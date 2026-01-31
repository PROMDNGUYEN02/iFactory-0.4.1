# File: presentation/viewmodels/gantt.py
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass(frozen=True, slots=True)
class GanttSegmentViewModel:
    """Single segment in the Gantt timeline."""

    start_time: datetime
    end_time: datetime
    status_code: int
    status_name: str
    status_color: str
    duration_seconds: float
    duration_display: str
    width_percent: float

    # Extended properties for modern UI
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
class GanttHourMark:
    """Hour marker for the timeline ruler."""

    hour: int
    x_percent: float
    is_major: bool
    label: str


@dataclass(frozen=True, slots=True)
class GanttStatsViewModel:
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
class GanttChartViewModel:
    """Complete Gantt chart data for a device."""

    device_code: str
    device_name: str
    segments: List[GanttSegmentViewModel]
    hour_marks: List[GanttHourMark]
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float
    stats: GanttStatsViewModel = field(default_factory=GanttStatsViewModel)
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
    def empty(device_code: str) -> "GanttChartViewModel":
        now = datetime.now()
        return GanttChartViewModel(
            device_code=device_code,
            device_name=device_code,
            segments=[],
            hour_marks=[],
            start_time=now,
            end_time=now,
            total_duration_seconds=0,
        )


__all__ = [
    "GanttSegmentViewModel",
    "GanttHourMark",
    "GanttStatsViewModel",
    "GanttChartViewModel",
]
