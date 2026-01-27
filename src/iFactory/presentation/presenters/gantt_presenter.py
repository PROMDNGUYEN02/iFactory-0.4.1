"""
Gantt Presenter - Formats Gantt data for UI display.
Pure transformation layer - NO domain imports.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from ..constants.ui_constants import StatusColors

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GanttSegmentViewModel:
    """Immutable view model for Gantt segment."""

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
    """Immutable view model for complete Gantt chart."""

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


class GanttPresenter:
    """Transforms segment DTOs into view models for display."""

    def __init__(self, theme: str = "light"):
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"

    def format_segment(
        self,
        start: datetime,
        end: datetime,
        status: str | int,
        total_duration: float,
    ) -> GanttSegmentViewModel:
        """Format single segment for display."""
        status_code = self._parse_status_code(status)
        duration = (end - start).total_seconds()
        width_pct = (duration / total_duration * 100) if total_duration > 0 else 0

        return GanttSegmentViewModel(
            start_time=start,
            end_time=end,
            status_code=status_code,
            status_name=StatusColors.get_name(status_code),
            status_display=StatusColors.get_name(status_code).upper(),
            status_color=StatusColors.get_color(status_code, self._theme),
            duration_seconds=duration,
            duration_display=self._format_duration(duration),
            width_percent=width_pct,
        )

    def format_segments(
        self,
        segments: List[Tuple[datetime, datetime, str | int]],
        start_time: datetime,
        end_time: datetime,
    ) -> List[GanttSegmentViewModel]:
        """Format multiple segments."""
        total_duration = (end_time - start_time).total_seconds()
        return [self.format_segment(start, end, status, total_duration) for (start, end, status) in segments]

    def format_chart(
        self,
        device_code: str,
        segments: List[Tuple[datetime, datetime, str | int]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> GanttChartViewModel:
        """Format complete Gantt chart."""
        now = datetime.now()
        start_time = start_time or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = end_time or now
        total_duration = (end_time - start_time).total_seconds()
        formatted_segments = self.format_segments(segments, start_time, end_time)

        return GanttChartViewModel(
            device_code=device_code,
            segments=formatted_segments,
            start_time=start_time,
            end_time=end_time,
            total_duration_seconds=total_duration,
        )

    def format_segment_tooltip(
        self,
        segment: GanttSegmentViewModel,
        device_code: str,
    ) -> str:
        """Format segment tooltip HTML."""
        return f"""
            <b>{device_code}</b><br>
            Status: {segment.status_display}<br>
            Start: {segment.start_display}<br>
            End: {segment.end_display}<br>
            Duration: {segment.duration_display}
        """.strip()

    def format_status_summary(
        self,
        segments: List[GanttSegmentViewModel],
    ) -> Dict[str, float]:
        """Calculate status duration summary."""
        summary: Dict[str, float] = {}
        for segment in segments:
            status = segment.status_name
            summary[status] = summary.get(status, 0) + segment.duration_seconds
        return summary

    def convert_to_tuples(
        self,
        segments: List[Any],
    ) -> List[Tuple[datetime, datetime, str]]:
        """Convert various segment formats to tuples."""
        converted = []
        for seg in segments:
            try:
                if hasattr(seg, "start_time") and hasattr(seg, "end_time"):
                    start = seg.start_time
                    end = seg.end_time
                    status = getattr(seg, "status_code", None) or getattr(seg, "status", "0")
                    converted.append((start, end, str(status)))
                elif isinstance(seg, dict):
                    start = seg.get("start_time") or seg.get("start")
                    end = seg.get("end_time") or seg.get("end")
                    status = seg.get("status_code") or seg.get("status") or "0"
                    if start and end:
                        converted.append((start, end, str(status)))
                elif isinstance(seg, (tuple, list)) and len(seg) >= 3:
                    converted.append((seg[0], seg[1], str(seg[2])))
            except Exception as e:
                logger.warning(f"[GanttPresenter] Failed to convert segment: {e}")
        return converted

    def _parse_status_code(self, status: str | int) -> int:
        if isinstance(status, int):
            return status
        try:
            return int(status)
        except (ValueError, TypeError):
            pass
        name_to_code = {
            "unknown": 0,
            "running": 1,
            "shutdown": 2,
            "stopped": 3,
            "stop": 3,
            "maintenance": 4,
            "alarm": 5,
        }
        return name_to_code.get(str(status).lower(), 0)

    @staticmethod
    def _format_duration(seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        else:
            return f"{int(seconds // 3600)}h {int(seconds % 3600 // 60)}m"


__all__ = ["GanttPresenter", "GanttSegmentViewModel", "GanttChartViewModel"]
