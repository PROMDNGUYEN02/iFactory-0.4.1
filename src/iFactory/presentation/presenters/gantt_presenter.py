"""
Gantt Presenter - Formats Gantt data for UI display.
Pure transformation layer - Encapsulates all display logic including duration calcs.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

from ..constants.ui_constants import StatusColors
from ..viewmodels.gantt_vm import GanttChartViewModel, GanttSegmentViewModel

logger = logging.getLogger(__name__)


class GanttPresenter:
    """
    Transforms segment DTOs into ViewModels.
    Calculates widths, formatted strings, and tooltips.
    """

    def __init__(self, theme: str = "light"):
        self._theme = theme

    def set_theme(self, theme: str) -> None:
        self._theme = "dark" if theme == "dark" else "light"

    def format_chart(
        self,
        device_code: str,
        segments_dto: List[Any],
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> GanttChartViewModel:
        """
        Main entry point: Transforms a list of DTOs into a full Chart ViewModel.
        Calculates relative percentages based on the time window.
        """
        now = datetime.now()
        start = window_start or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = window_end or now
        total_seconds = (end - start).total_seconds()

        # Normalize Input DTOs to tuples
        normalized_segments = self._normalize_dtos(segments_dto)

        formatted_segments = []
        for seg_start, seg_end, status_val in normalized_segments:
            # Clamp segments to window? (Optional logic, currently strictly formatting)
            # Calculate display properties
            duration = (seg_end - seg_start).total_seconds()
            percent = (duration / total_seconds) if total_seconds > 0 else 0

            # Resolve status
            status_code = self._parse_status_code(status_val)

            vm = GanttSegmentViewModel(
                start_time=seg_start,
                end_time=seg_end,
                status_code=status_code,
                status_name=StatusColors.get_name(status_code),
                status_display=StatusColors.get_name(status_code).upper(),
                status_color=StatusColors.get_color(status_code, self._theme),
                duration_seconds=duration,
                duration_display=self._format_duration(duration),
                width_percent=percent,
            )
            formatted_segments.append(vm)

        return GanttChartViewModel(
            device_code=device_code, segments=formatted_segments, start_time=start, end_time=end, total_duration_seconds=total_seconds
        )

    def _normalize_dtos(self, segments: List[Any]) -> List[Tuple[datetime, datetime, str]]:
        """Safely extract (start, end, status) from heterogeneous DTOs."""
        converted = []
        for seg in segments:
            try:
                # Handle Dict
                if isinstance(seg, dict):
                    s = seg.get("start_time") or seg.get("start")
                    e = seg.get("end_time") or seg.get("end")
                    st = seg.get("status_code") or seg.get("status", "0")
                # Handle DTO Object
                else:
                    s = getattr(seg, "start_time", None)
                    e = getattr(seg, "end_time", None)
                    st = getattr(seg, "status_code", getattr(seg, "status", "0"))

                if s and e:
                    # Ensure datetime types
                    if isinstance(s, str):
                        s = datetime.fromisoformat(s)
                    if isinstance(e, str):
                        e = datetime.fromisoformat(e)
                    converted.append((s, e, str(st)))
            except Exception as e:
                logger.debug(f"Skipping malformed segment: {e}")
                continue
        return converted

    def _parse_status_code(self, status: Union[str, int]) -> int:
        if isinstance(status, int):
            return status
        try:
            return int(status)
        except (ValueError, TypeError):
            pass

        # Fallback mapping for string statuses
        mapping = {"unknown": 0, "running": 1, "shutdown": 2, "stopped": 3, "stop": 3, "maintenance": 4, "alarm": 5}
        return mapping.get(str(status).lower(), 0)

    def _format_duration(self, seconds: float) -> str:
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds // 60)}m {int(seconds % 60)}s"
        return f"{int(seconds // 3600)}h {int(seconds % 3600 // 60)}m"
