"""
Gantt Utilities - Presentation Layer (Qt)

Optimized utility functions for Gantt chart calculations.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

__all__ = ["format_duration", "calculate_hour_step", "calculate_ticks", "time_to_x", "x_to_time", "calculate_segment_rect"]


def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted string (e.g., "2h 30m", "45m 12s", "30s")

    Examples:
        >>> format_duration(9000)
        '2h 30m'
        >>> format_duration(90)
        '1m 30s'
    """
    s = int(max(0, seconds) + 0.5)
    (h, remainder) = divmod(s, 3600)
    (m, sec) = divmod(remainder, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {sec}s"
    return f"{sec}s"


def calculate_hour_step(chart_width: float, min_spacing: float = 50.0) -> int:
    """
    Calculate optimal hour step for axis labels.

    Args:
        chart_width: Width of chart in pixels
        min_spacing: Minimum spacing between labels in pixels

    Returns:
        Hour step (1, 2, 3, 4, 6, 8, or 12)
    """
    if chart_width <= 0:
        return 6
    pph = chart_width / 24.0
    step = max(1, int(min_spacing / max(1.0, pph)))
    for candidate in (1, 2, 3, 4, 6, 8, 12):
        if step <= candidate:
            return candidate
    return 12


def calculate_ticks(start: datetime, end: datetime, step_hours: int) -> List[datetime]:
    """
    Calculate tick positions for time axis.

    Args:
        start: Timeline start time
        end: Timeline end time
        step_hours: Hour step between ticks

    Returns:
        List of datetime ticks
    """
    first = start.replace(minute=0, second=0, microsecond=0)
    if first < start:
        first += timedelta(hours=1)
    step = timedelta(hours=step_hours)
    ticks = []
    current = first
    while current <= end:
        ticks.append(current)
        current += step
    return ticks


def time_to_x(t: datetime, start: datetime, end: datetime, left: float, width: float) -> float:
    """
    Convert time to x coordinate.

    Args:
        t: Time to convert
        start: Timeline start
        end: Timeline end
        left: Chart left edge in pixels
        width: Chart width in pixels

    Returns:
        X coordinate in pixels
    """
    total = (end - start).total_seconds() or 1.0
    pos = max(0.0, min(total, (t - start).total_seconds()))
    return left + width * (pos / total)


def x_to_time(x: float, start: datetime, end: datetime, left: float, width: float) -> Optional[datetime]:
    """
    Convert x coordinate to time.

    Args:
        x: X coordinate in pixels
        start: Timeline start
        end: Timeline end
        left: Chart left edge in pixels
        width: Chart width in pixels

    Returns:
        Corresponding datetime or None if invalid
    """
    if width <= 0:
        return None
    ratio = max(0.0, min(1.0, (x - left) / width))
    delta = (end - start).total_seconds()
    return start + timedelta(seconds=delta * ratio)


def calculate_segment_rect(
    seg_start: datetime, seg_end: datetime, time_start: datetime, time_end: datetime, left: float, top: float, width: float, height: float
) -> Tuple[float, float, float, float]:
    """
    Calculate segment rectangle coordinates.

    Args:
        seg_start: Segment start time
        seg_end: Segment end time
        time_start: Timeline start
        time_end: Timeline end
        left: Chart left edge
        top: Chart top edge
        width: Chart width
        height: Chart height

    Returns:
        Tuple of (x, y, width, height) or (0, 0, 0, 0) if not visible
    """
    x1 = time_to_x(seg_start, time_start, time_end, left, width)
    x2 = time_to_x(seg_end, time_start, time_end, left, width)
    right = left + width
    if x2 <= left or x1 >= right:
        return (0, 0, 0, 0)
    x1 = max(x1, left)
    x2 = min(x2, right)
    return (x1, top, max(1.0, x2 - x1), height)
