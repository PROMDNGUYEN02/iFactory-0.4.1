"""
Generate Production Timeline Query.
Uses Cold Storage for history data.
"""

from datetime import datetime
from typing import List, Callable

from iFactory.application.ports.cache import ICacheProvider


class GenerateProductionTimelineQuery:
    """
    QUERY: Fetches production history from Cold Storage and formats it as a timeline.
    Read-only, no domain mutation.
    """

    def __init__(
        self,
        uow_factory: Callable,  # Returns ColdStorageUnitOfWork
        cache: ICacheProvider,
    ):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
        fill_gaps: bool = True,
    ) -> List[dict]:
        """
        Executes the timeline generation query using Cold Storage.
        """
        # Try cache first
        cache_key = f"timeline_{equip_code}_{start_time.isoformat()}_{end_time.isoformat()}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        async with self._uow_factory() as uow:
            # Get history from Cold Storage (via history repository)
            history = await uow.history.get_history(equip_code, start_time, end_time)

        segments = []
        for h in history:
            # Handle open period (not yet ended) -> end_time = chart end or now
            segment_end = h.end_time if h.end_time else end_time

            # Clip to chart boundaries
            valid_start = max(h.start_time, start_time)
            valid_end = min(segment_end, end_time)

            if valid_start < valid_end:
                segments.append(
                    {
                        "equip_code": h.device_code,
                        "status_code": str(h.status_code),  # Convert to string
                        "status_name": h.status_name,
                        "start_time": valid_start,
                        "end_time": valid_end,
                    }
                )

        # Cache for 30 seconds
        await self._cache.set(cache_key, segments, ttl=30)

        return segments
