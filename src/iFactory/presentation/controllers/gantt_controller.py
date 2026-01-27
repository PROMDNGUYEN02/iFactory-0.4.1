from datetime import datetime
from typing import Optional

from PySide6.QtCore import QObject, Slot, Signal

from iFactory.application.use_cases.queries.production_queries import ProductionQueries
from iFactory.application.dto.timeline_dto import TimelineDTO
from iFactory.presentation.adapters.async_executor import AsyncExecutor
from iFactory.presentation.viewmodels.gantt_viewmodel import GanttViewModel


class GanttController(QObject):
    """
    Controller for Production Timeline use cases.
    """

    timeline_loaded = Signal(GanttViewModel)

    def __init__(self, executor: AsyncExecutor, queries: ProductionQueries, parent=None):
        super().__init__(parent)
        self._executor = executor
        self._queries = queries
        self._selected_device: Optional[str] = None

    @Slot(str)
    def select_device(self, equipment_code: str):
        self._selected_device = equipment_code
        self.refresh_timeline()

    @Slot()
    def refresh_timeline(self):
        if not self._selected_device:
            return

        self._executor.run(
            self._queries.get_last_24h_timeline(self._selected_device),
            on_success=self._on_timeline_loaded,
            on_error=lambda err: print(f"Timeline error: {err}"),
        )

    def _on_timeline_loaded(self, dto: TimelineDTO):
        vm = GanttViewModel.from_dto(dto)
        self.timeline_loaded.emit(vm)
