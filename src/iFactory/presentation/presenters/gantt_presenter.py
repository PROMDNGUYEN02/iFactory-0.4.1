# File: presentation/presenters/gantt_presenter.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from ..constants.status import Status
from ..viewmodels.gantt import (
    GanttChartViewModel,
    GanttHourMark,
    GanttSegmentViewModel,
    GanttStatsViewModel,
)

logger = logging.getLogger(__name__)


# Modern color palette with gradients
STATUS_GRADIENTS: Dict[int, Tuple[str, str]] = {
    0: ("#94A3B8", "#64748B"),  # Unknown - Slate
    1: ("#34D399", "#059669"),  # Running - Emerald
    2: ("#60A5FA", "#3B82F6"),  # Shutdown - Blue
    3: ("#FBBF24", "#D97706"),  # Stopped - Amber
    4: ("#A78BFA", "#7C3AED"),  # Maintenance - Violet
    5: ("#F87171", "#DC2626"),  # Alarm - Red
}


class GanttPresenter:
    """Presenter for transforming raw data into Gantt ViewModels."""

    def present_device_chart(
        self,
        device_code: str,
        device_name: str,
        segments_dto: List[Any],
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> GanttChartViewModel:
        """
        Create a complete Gantt chart ViewModel for a single device.
        Optimized for 24-hour display.
        """
        now = datetime.now()
        end = window_end or now
        start = window_start or (end - timedelta(hours=24))
        total_seconds = max((end - start).total_seconds(), 1)

        # Normalize and process segments
        normalized = self._normalize_segments(segments_dto)
        segments = self._create_segment_viewmodels(normalized, start, end, total_seconds)

        # Generate hour marks for ruler
        hour_marks = self._generate_hour_marks(start, end, total_seconds)

        # Calculate statistics
        stats = self._calculate_stats(segments, total_seconds)

        # Get current status
        current_status, current_color = self._get_current_status(segments, now)

        return GanttChartViewModel(
            device_code=device_code,
            device_name=device_name,
            segments=segments,
            hour_marks=hour_marks,
            start_time=start,
            end_time=end,
            total_duration_seconds=total_seconds,
            stats=stats,
            current_status=current_status,
            current_status_color=current_color,
        )

    def present_chart(
        self,
        device_code: str,
        segments_dto: List[Any],
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> GanttChartViewModel:
        """Legacy method for compatibility with multi-device view."""
        return self.present_device_chart(
            device_code=device_code,
            device_name=device_code,
            segments_dto=segments_dto,
            window_start=window_start,
            window_end=window_end,
        )

    def _normalize_segments(self, segments: List[Any]) -> List[Tuple[datetime, datetime, int]]:
        """Normalize raw segment data into consistent tuples."""
        result: List[Tuple[datetime, datetime, int]] = []

        for seg in segments:
            try:
                if isinstance(seg, dict):
                    s = seg.get("start_time") or seg.get("start")
                    e = seg.get("end_time") or seg.get("end")
                    st = seg.get("status_code") or seg.get("status", 0)
                else:
                    s = getattr(seg, "start_time", None)
                    e = getattr(seg, "end_time", None)
                    st = getattr(seg, "status_code", getattr(seg, "status", 0))

                if s and e:
                    if isinstance(s, str):
                        s = datetime.fromisoformat(s)
                    if isinstance(e, str):
                        e = datetime.fromisoformat(e)

                    status_code = self._parse_status(st)
                    result.append((s, e, status_code))
            except Exception as ex:
                logger.debug("Skipping malformed segment: %s", ex)

        # Sort by start time
        result.sort(key=lambda x: x[0])
        return result

    def _create_segment_viewmodels(
        self,
        normalized: List[Tuple[datetime, datetime, int]],
        start: datetime,
        end: datetime,
        total_seconds: float,
    ) -> List[GanttSegmentViewModel]:
        """Create ViewModel objects from normalized data."""
        now = datetime.now()
        segments: List[GanttSegmentViewModel] = []

        for seg_start, seg_end, status_code in normalized:
            # Clip to window
            if seg_end < start or seg_start > end:
                continue

            clipped_start = max(seg_start, start)
            clipped_end = min(seg_end, end)

            duration = (clipped_end - clipped_start).total_seconds()
            if duration <= 0:
                continue

            width_percent = duration / total_seconds
            gradient = STATUS_GRADIENTS.get(status_code, STATUS_GRADIENTS[0])

            # Check if this is the current segment
            is_current = clipped_start <= now <= clipped_end

            vm = GanttSegmentViewModel(
                start_time=clipped_start,
                end_time=clipped_end,
                status_code=status_code,
                status_name=Status.get_name(status_code),
                status_color=Status.get_color(status_code),
                duration_seconds=duration,
                duration_display=self._format_duration(duration),
                width_percent=width_percent,
                gradient_start=gradient[0],
                gradient_end=gradient[1],
                is_current=is_current,
            )
            segments.append(vm)

        return segments

    def _generate_hour_marks(
        self,
        start: datetime,
        end: datetime,
        total_seconds: float,
    ) -> List[GanttHourMark]:
        """Generate hour marks for the timeline ruler."""
        marks: List[GanttHourMark] = []

        # Start from the beginning of the first hour
        current = start.replace(minute=0, second=0, microsecond=0)
        if current < start:
            current += timedelta(hours=1)

        while current <= end:
            offset_seconds = (current - start).total_seconds()
            x_percent = offset_seconds / total_seconds

            hour = current.hour
            is_major = hour % 6 == 0  # 00:00, 06:00, 12:00, 18:00

            label = current.strftime("%H:%M") if is_major else current.strftime("%H")

            marks.append(
                GanttHourMark(
                    hour=hour,
                    x_percent=x_percent,
                    is_major=is_major,
                    label=label,
                )
            )

            current += timedelta(hours=1)

        return marks

    def _calculate_stats(
        self,
        segments: List[GanttSegmentViewModel],
        total_seconds: float,
    ) -> GanttStatsViewModel:
        """Calculate statistics from segments."""
        running = stopped = alarm = maintenance = shutdown = 0.0

        for seg in segments:
            duration = seg.duration_seconds
            if seg.status_code == 1:
                running += duration
            elif seg.status_code == 2:
                shutdown += duration
            elif seg.status_code == 3:
                stopped += duration
            elif seg.status_code == 4:
                maintenance += duration
            elif seg.status_code == 5:
                alarm += duration

        # Calculate percentages
        running_pct = (running / total_seconds * 100) if total_seconds > 0 else 0
        stopped_pct = (stopped / total_seconds * 100) if total_seconds > 0 else 0
        alarm_pct = (alarm / total_seconds * 100) if total_seconds > 0 else 0

        # Simple OEE estimate (running time / available time)
        available = total_seconds - shutdown - maintenance
        oee = (running / available * 100) if available > 0 else 0

        return GanttStatsViewModel(
            total_running_seconds=running,
            total_stopped_seconds=stopped,
            total_alarm_seconds=alarm,
            total_maintenance_seconds=maintenance,
            total_shutdown_seconds=shutdown,
            running_percent=running_pct,
            stopped_percent=stopped_pct,
            alarm_percent=alarm_pct,
            oee_estimate=oee,
        )

    def _get_current_status(
        self,
        segments: List[GanttSegmentViewModel],
        now: datetime,
    ) -> Tuple[str, str]:
        """Get the current status from segments."""
        for seg in reversed(segments):
            if seg.is_current or seg.end_time >= now:
                return seg.status_name, seg.status_color

        if segments:
            last = segments[-1]
            return last.status_name, last.status_color

        return "Unknown", "#64748B"

    def _parse_status(self, status: Any) -> int:
        """Parse status to integer code."""
        if isinstance(status, int):
            return status
        try:
            return int(status)
        except (ValueError, TypeError):
            pass

        mapping = {
            "unknown": 0,
            "running": 1,
            "shutdown": 2,
            "stopped": 3,
            "stop": 3,
            "maintenance": 4,
            "alarm": 5,
        }
        return mapping.get(str(status).lower(), 0)

    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"


__all__ = ["GanttPresenter"]
