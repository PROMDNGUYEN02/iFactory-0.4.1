from dataclasses import dataclass
from datetime import datetime
from typing import List


@dataclass(frozen=True)
class GanttBarDTO:
    """
    Represents a single bar on the Gantt chart.
    """

    status_code: int
    status_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float


@dataclass(frozen=True)
class TimelineDTO:
    """
    Collection of timeline bars for a specific device.
    """

    equipment_code: str
    bars: List[GanttBarDTO]
