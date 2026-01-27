"""
Gantt Controller - Handles Gantt chart data fetching.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, List, Any

from PySide6.QtCore import QObject

from ..ui_state.actions import UIActionType, load_gantt
from ..ui_state.store import Action

if TYPE_CHECKING:
    from ..presenters.gantt_presenter import GanttPresenter
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class GanttController(QObject):
    """Coordinates Gantt timeline data between Application layer and UI State."""

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
        """Load Gantt timeline for devices (24h)."""
        try:
            if not self._device_service:
                logger.warning("[GanttController] No device service available.")
                return {}

            end = datetime.now()
            start = end - timedelta(days=days)
            total_seconds = (end - start).total_seconds()

            # Get devices from store
            state = self._store.get_state()
            devices = state.get("devices", {})

            if not devices:
                logger.debug("[GanttController] No devices in store.")
                return {}

            timeline_data = {}

            # Limit to first 20 devices for performance
            device_codes = list(devices.keys())[:20]

            for code in device_codes:
                try:
                    result = await self._device_service.generate_gantt_segments(code, days=days)
                    segments_dto = result.get("segments", [])

                    if not segments_dto:
                        continue

                    formatted_segments = []
                    for seg in segments_dto:
                        seg_start = seg.get("start_time", start)
                        seg_end = seg.get("end_time", end)

                        # Ensure datetime objects
                        if isinstance(seg_start, str):
                            seg_start = datetime.fromisoformat(seg_start)
                        if isinstance(seg_end, str):
                            seg_end = datetime.fromisoformat(seg_end)

                        duration = (seg_end - seg_start).total_seconds()
                        percent = duration / total_seconds if total_seconds > 0 else 0

                        status_code = seg.get("status_code", "0")

                        formatted_segments.append(
                            {
                                "start_time": seg_start,
                                "end_time": seg_end,
                                "status_name": seg.get("status_name", "Unknown"),
                                "status_code": str(status_code),
                                "percent": percent,
                            }
                        )

                    if formatted_segments:
                        timeline_data[code] = formatted_segments

                except Exception as e:
                    logger.debug(f"No gantt data for {code}: {e}")

            # Dispatch to store
            if timeline_data:
                self._store.dispatch(load_gantt(timeline_data))
                logger.debug(f"[GanttController] Loaded timeline for {len(timeline_data)} devices.")

            return timeline_data

        except Exception as e:
            logger.error(f"[GanttController] Failed to load timeline: {e}", exc_info=True)
            return {}


__all__ = ["GanttController"]
