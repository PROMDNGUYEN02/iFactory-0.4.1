"""
Gantt Controller - Handles Gantt chart data loading.
Single Responsibility: Orchestrate data flow (Service -> Presenter -> Store).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any

from PySide6.QtCore import QObject

from ..ui_state.actions import load_gantt

if TYPE_CHECKING:
    from ..presenters.gantt_presenter import GanttPresenter
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class GanttController(QObject):
    """
    Coordinates loading of Gantt timeline data.
    Delegates all formatting and calculation to GanttPresenter.
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

    async def load_timeline(self, days: int = 1) -> Dict[str, Any]:
        """
        Execute Use Case: Load Gantt Timeline.
        Flow:
        1. Determine Time Window
        2. Identify Targets (Devices)
        3. Fetch Data (Service)
        4. Transform Data (Presenter)
        5. Update UI (Store)
        """
        try:
            if not self._device_service:
                return {}

            # 1. Define Window
            end = datetime.now()
            start = end - timedelta(days=days)

            # 2. Identify Targets (from State)
            state = self._store.get_state()
            devices = state.get("devices", {})
            if not devices:
                return {}

            # Limit scope to prevent UI overload
            target_codes = list(devices.keys())[:20]

            timeline_vms = {}

            # 3. Orchestrate Fetch & Transform
            for code in target_codes:
                try:
                    # Service Call
                    result = await self._device_service.generate_gantt_segments(code, days=days)
                    segments_dto = result.get("segments", [])

                    if not segments_dto:
                        continue

                    # Presenter Call (Pure Transformation)
                    vm = self._presenter.format_chart(device_code=code, segments_dto=segments_dto, window_start=start, window_end=end)

                    # Store Adapter: Convert VM to legacy Dict format if needed,
                    # or store VM directly if Store supports it.
                    # Mapping VM to list of dicts for serialization safety
                    timeline_vms[code] = [
                        {
                            "start_time": s.start_time,
                            "end_time": s.end_time,
                            "status_name": s.status_name,
                            "status_code": str(s.status_code),
                            "percent": s.width_percent,
                        }
                        for s in vm.segments
                    ]

                except Exception as e:
                    logger.debug(f"Gantt fetch failed for {code}: {e}")

            # 4. Dispatch
            if timeline_vms:
                self._store.dispatch(load_gantt(timeline_vms))
                logger.debug(f"[GanttController] Updated {len(timeline_vms)} timelines")

            return timeline_vms

        except Exception as e:
            logger.error(f"[GanttController] Fatal error: {e}", exc_info=True)
            return {}
