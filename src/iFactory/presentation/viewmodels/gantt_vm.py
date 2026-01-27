"""Gantt ViewModel - Pure read-only data structures for timeline UI."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass(frozen=True)
class GanttSegmentVM:
    """Immutable segment for Gantt display."""

    start_time: str
    end_time: str
    status_name: str
    status_code: str
    color: str
    percent: float
    duration_display: str = ""


@dataclass(frozen=True)
class GanttTimelineVM:
    """Immutable timeline for a single device."""

    device_code: str
    segments: List[GanttSegmentVM]
    total_duration_display: str = ""


__all__ = ["GanttSegmentVM", "GanttTimelineVM"]
