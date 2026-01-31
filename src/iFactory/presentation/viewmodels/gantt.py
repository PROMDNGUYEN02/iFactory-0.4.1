# File: presentation/viewmodels/gantt.py
from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True, slots=True)
class GanttSegmentViewModel:
    start_time: datetime
    end_time: datetime
    status_code: int
    status_name: str
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


@dataclass(frozen=True, slots=True)
class GanttChartViewModel:
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

    @staticmethod
    def empty(device_code: str) -> "GanttChartViewModel":
        now = datetime.now()
        return GanttChartViewModel(
            device_code=device_code,
            segments=[],
            start_time=now,
            end_time=now,
            total_duration_seconds=0,
        )
