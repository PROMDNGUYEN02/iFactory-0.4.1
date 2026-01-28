"""
Gantt ViewModel - Pure read-only data structures for timeline UI.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class GanttSegmentViewModel:
    """
    Immutable model for a single block on the Gantt chart.
    Contains pre-calculated display properties (width, color).
    """

    start_time: datetime
    end_time: datetime
    status_code: int
    status_name: str
    status_display: str
    status_color: str
    duration_seconds: float
    duration_display: str
    width_percent: float

    @property
    def start_display(self) -> str:
        return self.start_time.strftime("%H:%M:%S")

    @property
    def end_display(self) -> str:
        return self.end_time.strftime("%H:%M:%S")


@dataclass(frozen=True)
class GanttChartViewModel:
    """
    Immutable model for a complete Device Timeline row.
    """

    device_code: str
    segments: List[GanttSegmentViewModel]
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float

    @property
    def segment_count(self) -> int:
        return len(self.segments)

    @property
    def time_range_display(self) -> str:
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"
