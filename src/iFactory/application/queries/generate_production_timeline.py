"""
Generate Production Timeline Query.
"""

from datetime import datetime
from typing import List, Callable, Any

from iFactory.application.ports.unit_of_work import IUnitOfWork
from iFactory.application.ports.cache import ICacheProvider


class GenerateProductionTimelineQuery:
    """
    QUERY: Fetches production history for a device and formats it as a timeline.
    Read-only, no domain mutation.
    """

    def __init__(self, unit_of_work_factory: Callable[[], IUnitOfWork], cache_provider: ICacheProvider):
        self._uow_factory = unit_of_work_factory
        self._cache = cache_provider

    async def execute(self, equip_code: str, start_time: datetime, end_time: datetime, fill_gaps: bool = True) -> List[dict]:
        """
        Executes the timeline generation query.
        """
        async with self._uow_factory() as uow:
            # Assumes the repository has a method to fetch history within a time range
            history = await uow.devices.get_history(equip_code)

        segments = []
        for h in history:
            # Application layer maps the domain entities into simple dictionary segments for the Gantt Chart
            # Any complex gap-filling logic should ideally reside in a Domain Service,
            # but mapping to UI structures happens here.
            segments.append(
                {
                    "equip_code": h.code,
                    "status_code": h.status,
                    "status_name": h.status_name,
                    "start_time": h.last_update,
                    "end_time": end_time,  # Placeholder for sequence logic
                }
            )

        return segments
