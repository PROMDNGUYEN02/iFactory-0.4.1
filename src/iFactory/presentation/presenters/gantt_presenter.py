"""
Gantt Presenter - Formats Gantt data for UI display.

Refactored: Added logic to convert DTOs to Gantt-specific tuple format
required by the GanttManager/View, moving this out of MainController.
Domain imports removed to maintain Clean Architecture.
"""

from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import List, Optional, Tuple


@dataclass(frozen=True)
class GanttSegmentViewModel:
    """View model for Gantt segment."""

    start_time: datetime
    end_time: datetime
    status_name: str
    status_display: str
    status_color: str
    duration_seconds: float
    duration_display: str
    width_percent: float

    @property
    def start_display(self) -> str:
        """Formatted start time."""
        return self.start_time.strftime("%H:%M:%S")

    @property
    def end_display(self) -> str:
        """Formatted end time."""
        return self.end_time.strftime("%H:%M:%S")


@dataclass(frozen=True)
class GanttChartViewModel:
    """View model for complete Gantt chart."""

    device_code: str
    segments: List[GanttSegmentViewModel]
    start_time: datetime
    end_time: datetime
    total_duration_seconds: float

    @property
    def segment_count(self) -> int:
        """Number of segments."""
        return len(self.segments)

    @property
    def time_range_display(self) -> str:
        """Display string for time range."""
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')}"


class GanttPresenter:
    """
    Presenter for Gantt chart data.

    Transforms segment DTOs into view models for display.
    """

    def __init__(self, theme: str = "light"):
        """
        Initialize presenter.

        Args:
            theme: Initial theme mode
        """
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        """Set theme mode."""
        self._theme = "dark" if theme == "dark" else "light"

    def format_segment(self, start: datetime, end: datetime, status: str, total_duration: float) -> GanttSegmentViewModel:
        """
        Format single segment for display.

        Args:
            start: Segment start time
            end: Segment end time
            status: Status code or name
            total_duration: Total chart duration in seconds

        Returns:
            GanttSegmentViewModel
        """
        from iFactory.domain.enums import DeviceStatus
        from iFactory.application.services.status_ui_mapper import StatusUIMapper
        
        status_obj = DeviceStatus.from_code_or_name(str(status))
        duration = (end - start).total_seconds()
        width_pct = duration / total_duration * 100 if total_duration > 0 else 0
        return GanttSegmentViewModel(
            start_time=start,
            end_time=end,
            status_name=status_obj.internal_name,
            status_display=status_obj.name.upper(),
            status_color=StatusUIMapper.get_color(status_obj.code, self._theme),
            duration_seconds=duration,
            duration_display=self._format_duration(duration),
            width_percent=width_pct,
        )

    def format_segments(
        self, segments: List[Tuple[datetime, datetime, str]], start_time: datetime, end_time: datetime
    ) -> List[GanttSegmentViewModel]:
        """
        Format multiple segments.

        Args:
            segments: List of (start, end, status) tuples
            start_time: Chart start time
            end_time: Chart end time

        Returns:
            List of GanttSegmentViewModel
        """
        total_duration = (end_time - start_time).total_seconds()
        return [self.format_segment(start, end, status, total_duration) for (start, end, status) in segments]

    def format_chart(
        self,
        device_code: str,
        segments: List[Tuple[datetime, datetime, str]],
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> GanttChartViewModel:
        """
        Format complete Gantt chart.

        Args:
            device_code: Device identifier
            segments: Segment data
            start_time: Chart start (default: today 00:00)
            end_time: Chart end (default: now)

        Returns:
            GanttChartViewModel
        """
        now = datetime.now()
        start_time = start_time or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time = end_time or now
        total_duration = (end_time - start_time).total_seconds()
        formatted_segments = self.format_segments(segments, start_time, end_time)
        return GanttChartViewModel(
            device_code=device_code, segments=formatted_segments, start_time=start_time, end_time=end_time, total_duration_seconds=total_duration
        )

    def format_segment_tooltip(self, segment: GanttSegmentViewModel, device_code: str) -> str:
        """
        Format segment tooltip HTML.

        Args:
            segment: Segment view model
            device_code: Device identifier

        Returns:
            HTML tooltip string
        """
        return f"""
            <b>{device_code}</b><br>
            Status: {segment.status_display}<br>
            Start: {segment.start_display}<br>
            End: {segment.end_display}<br>
            Duration: {segment.duration_display}
        """.strip()

    def format_segment_details(self, segment: GanttSegmentViewModel, device_code: str) -> str:
        """
        Format segment details for dialog.

        Args:
            segment: Segment view model
            device_code: Device identifier

        Returns:
            Multi-line details string
        """
        return f"Device: {device_code}\nStatus: {segment.status_display}\nStart: {segment.start_display}\nEnd: {segment.end_display}\nDuration: {segment.duration_display}"

    def format_status_summary(self, segments: List[GanttSegmentViewModel]) -> dict[str, float]:
        """
        Calculate status duration summary.

        Args:
            segments: List of segment view models

        Returns:
            Dict of status_name -> total_seconds
        """
        summary: dict[str, float] = {}
        for segment in segments:
            status = segment.status_name
            summary[status] = summary.get(status, 0) + segment.duration_seconds
        return summary

    def format_status_percentages(self, segments: List[GanttSegmentViewModel], total_seconds: float) -> dict[str, float]:
        """
        Calculate status percentages.

        Args:
            segments: List of segments
            total_seconds: Total duration

        Returns:
            Dict of status_name -> percentage
        """
        summary = self.format_status_summary(segments)
        if total_seconds <= 0:
            return {k: 0.0 for k in summary}
        return {status: duration / total_seconds * 100 for (status, duration) in summary.items()}

    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            minutes = int(seconds // 60)
            secs = int(seconds % 60)
            return f"{minutes}m {secs}s"
        else:
            hours = int(seconds // 3600)
            minutes = int(seconds % 3600 // 60)
            return f"{hours}h {minutes}m"

    # --- Refactored Logic from MainController ---

    def convert_to_tuples(self, segments: List[Any]) -> List[Tuple[datetime, datetime, str]]:
        """
        Convert various segment formats to tuples.

        Refactored from MainController._convert_segments_to_tuples.
        Handles:
        - GanttSegmentDTO objects
        - Dict with start_time/end_time keys
        - Already tuple/list format

        Returns:
            List of (start, end, status_code) tuples
        """
        converted = []
        for seg in segments:
            try:
                if hasattr(seg, "start_time") and hasattr(seg, "end_time"):
                    start = seg.start_time
                    end = seg.end_time
                    status = getattr(seg, "status_code", None) or getattr(seg, "status", "unknown")
                    converted.append((start, end, str(status)))
                elif isinstance(seg, dict):
                    start = seg.get("start_time") or seg.get("start")
                    end = seg.get("end_time") or seg.get("end")
                    status = seg.get("status_code") or seg.get("status") or seg.get("status_name", "unknown")
                    if start and end:
                        converted.append((start, end, str(status)))
                elif isinstance(seg, (tuple, list)) and len(seg) >= 3:
                    converted.append((seg[0], seg[1], str(seg[2])))
                elif isinstance(seg, (tuple, list)) and len(seg) == 2:
                    converted.append((seg[0], seg[1], "unknown"))
                else:
                    logger.warning(f"[GanttPresenter] Unknown segment format: {type(seg)}")
            except Exception as e:
                logger.warning(f"[GanttPresenter] Failed to convert segment: {e}")
                continue
        return converted


__all__ = ["GanttPresenter", "GanttSegmentViewModel", "GanttChartViewModel"]
