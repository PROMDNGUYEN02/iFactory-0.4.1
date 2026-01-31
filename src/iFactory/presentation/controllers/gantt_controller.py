# File: presentation/controllers/gantt_controller.py
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import QObject

from ..adapters.async_executor import AsyncExecutor
from ..state.actions import load_gantt

if TYPE_CHECKING:
    from ..presenters.gantt_presenter import GanttPresenter
    from ..state.store import Store

logger = logging.getLogger(__name__)


class GanttController(QObject):
    def __init__(
        self,
        device_service,
        presenter: "GanttPresenter",
        store: "Store",
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._service = device_service
        self._presenter = presenter
        self._store = store

        self._executor = AsyncExecutor(max_workers=2, parent=self)

    def load_timeline(self, days: int = 1) -> None:
        self._executor.execute(
            self._fetch_timeline(days),
            on_success=self._on_fetch_success,
            on_error=self._on_fetch_error,
        )

    async def _fetch_timeline(self, days: int) -> Dict[str, Any]:
        if not self._service:
            return {}

        end = datetime.now()
        start = end - timedelta(days=days)

        state = self._store.get_state()
        devices = state.get("devices", {})
        if not devices:
            return {}

        target_codes = list(devices.keys())[:20]
        result: Dict[str, Any] = {}

        for code in target_codes:
            try:
                data = await self._service.generate_gantt_segments(code, days=days)
                segments = data.get("segments", [])
                if segments:
                    vm = self._presenter.present_chart(code, segments, start, end)
                    result[code] = vm.segments
            except Exception as e:
                logger.debug("Gantt fetch failed for %s: %s", code, e)

        return result

    def _on_fetch_success(self, data: Dict[str, Any]) -> None:
        if data:
            self._store.dispatch(load_gantt(data))
            logger.debug("Gantt updated for %d devices", len(data))

    def _on_fetch_error(self, error: Exception) -> None:
        logger.error("Gantt fetch failed: %s", error)

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False)
