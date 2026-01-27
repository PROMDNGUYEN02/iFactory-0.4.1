from datetime import datetime, timedelta
from typing import List

from iFactory.application.dto.timeline_dto import TimelineDTO, GanttBarDTO
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.time_range import TimeRange


class ProductionQueries:
    """
    Read-only use cases for Production History and Gantt Charts.
    """

    def __init__(self, uow: AbstractUnitOfWork):
        self._uow = uow

    async def get_timeline(
        self,
        code: str,
        start: datetime,
        end: datetime,
    ) -> TimelineDTO:
        """
        Retrieves the status timeline for a device within a window.
        """
        async with self._uow as uow:
            try:
                e_code = EquipmentCode(code)
                window = TimeRange(start, end)

                history = await uow.production.get_status_history(e_code, window)

                bars = []
                for period in history:
                    # Clip period to window for display purposes
                    intersection = period.time_range.intersection(window)
                    if intersection:
                        bars.append(
                            GanttBarDTO(
                                status_code=period.status.value,
                                status_name=period.status.name,
                                start_time=intersection.start,
                                end_time=intersection.end or datetime.now(),
                                duration_seconds=intersection.duration_seconds,
                            )
                        )

                return TimelineDTO(equipment_code=code, bars=bars)

            except Exception:
                return TimelineDTO(equipment_code=code, bars=[])

    async def get_last_24h_timeline(self, code: str) -> TimelineDTO:
        end = datetime.now()
        start = end - timedelta(hours=24)
        return await self.get_timeline(code, start, end)
