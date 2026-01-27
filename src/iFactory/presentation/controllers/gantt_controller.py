"""
Gantt Controller - Handles Gantt chart data fetching use case.
Single Responsibility: Load and format timeline data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Any

from PySide6.QtCore import QObject

from ..ui_state.actions import UIActionType
from ..ui_state.store import Action

if TYPE_CHECKING:
    from ..presenters.gantt_presenter import GanttPresenter
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class GanttController(QObject):
    """
    Coordinates Gantt timeline data between Application layer and UI State.
    """

    def __init__(
        self,
        device_service,
        presenter: "GanttPresenter",
        store: "Store",
        parent=None,
    ):
        super().__init__(parent)
        self._device_service = device_service
        self._presenter = presenter
        self._store = store

    async def load_timeline(self, days: int = 1) -> Dict[str, List[Any]]:
        """
        Load Gantt timeline for all devices.
        Returns formatted timeline data.
        """
        try:
            end = datetime.now()
            start = end - timedelta(days=days)
            total_seconds = (end - start).total_seconds()

            devices = self._store.get_state().get("devices", {})
            timeline_data = {}

            for code in devices.keys():
                result = await self._device_service.generate_gantt_segments(code, days=days)
                segments_dto = result.get("segments", [])

                formatted_segments = []
                for seg in segments_dto:
                    seg_start = seg.get("start_time", start)
                    seg_end = seg.get("end_time", end)
                    duration = (seg_end - seg_start).total_seconds()
                    percent = duration / total_seconds if total_seconds > 0 else 0

                    status_code = seg.get("status_code", 0)
                    vm = self._presenter.format_segment(
                        start=seg_start,
                        end=seg_end,
                        status=status_code,
                        total_duration=total_seconds,
                    )

                    formatted_segments.append(
                        {
                            "start_time": vm.start_display,
                            "end_time": vm.end_display,
                            "status_name": vm.status_name,
                            "status_code": str(vm.status_code),
                            "color": vm.status_color,
                            "percent": percent,
                        }
                    )

                timeline_data[code] = formatted_segments

            self._store.dispatch(
                Action(
                    type=UIActionType.GANTT_LOADED.value,
                    payload=timeline_data,
                )
            )

            logger.debug(f"[GanttController] Loaded timeline for {len(timeline_data)} devices.")
            return timeline_data

        except Exception as e:
            logger.error(f"[GanttController] Failed to load timeline: {e}", exc_info=True)
            return {}


__all__ = ["GanttController"]
