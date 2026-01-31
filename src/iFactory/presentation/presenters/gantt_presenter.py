# File: presentation/presenters/gantt_presenter.py
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional, Tuple

from ..constants.status import Status
from ..viewmodels.gantt import GanttChartViewModel, GanttSegmentViewModel

logger = logging.getLogger(__name__)


class GanttPresenter:
    def present_chart(
        self,
        device_code: str,
        segments_dto: List[Any],
        window_start: Optional[datetime] = None,
        window_end: Optional[datetime] = None,
    ) -> GanttChartViewModel:
        now = datetime.now()
        start = window_start or now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = window_end or now
        total_seconds = max((end - start).total_seconds(), 1)

        normalized = self._normalize_segments(segments_dto)
        formatted: List[GanttSegmentViewModel] = []

        for seg_start, seg_end, status_val in normalized:
            duration = (seg_end - seg_start).total_seconds()
            percent = duration / total_seconds
            status_code = self._parse_status(status_val)

            vm = GanttSegmentViewModel(
                start_time=seg_start,
                end_time=seg_end,
                status_code=status_code,
                status_name=Status.get_name(status_code),
                status_color=Status.get_color(status_code),
                duration_seconds=duration,
                duration_display=self._format_duration(duration),
                width_percent=percent,
            )
            formatted.append(vm)

        return GanttChartViewModel(
            device_code=device_code,
            segments=formatted,
            start_time=start,
            end_time=end,
            total_duration_seconds=total_seconds,
        )

    def _normalize_segments(self, segments: List[Any]) -> List[Tuple[datetime, datetime, str]]:
        result: List[Tuple[datetime, datetime, str]] = []

        for seg in segments:
            try:
                if isinstance(seg, dict):
                    s = seg.get("start_time") or seg.get("start")
                    e = seg.get("end_time") or seg.get("end")
                    st = seg.get("status_code") or seg.get("status", "0")
                else:
                    s = getattr(seg, "start_time", None)
                    e = getattr(seg, "end_time", None)
                    st = getattr(seg, "status_code", getattr(seg, "status", "0"))

                if s and e:
                    if isinstance(s, str):
                        s = datetime.fromisoformat(s)
                    if isinstance(e, str):
                        e = datetime.fromisoformat(e)
                    result.append((s, e, str(st)))
            except Exception as ex:
                logger.debug("Skipping malformed segment: %s", ex)

        return result

    def _parse_status(self, status: Any) -> int:
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
        if seconds < 60:
            return f"{int(seconds)}s"
        if seconds < 3600:
            m, s = divmod(int(seconds), 60)
            return f"{m}m {s}s"
        h, rem = divmod(int(seconds), 3600)
        m = rem // 60
        return f"{h}h {m}m"
