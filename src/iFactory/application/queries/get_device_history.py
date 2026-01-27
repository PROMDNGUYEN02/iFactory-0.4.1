"""
Get Device History Query.
Uses Cold Storage for historical data.
Supports 24h, 7d, 30d, 60d retention periods.
"""

from datetime import datetime, timedelta
from typing import List, Callable, Optional

from iFactory.application.dto.device_dto import DeviceHistoryDTO
from iFactory.application.ports.cache import ICacheProvider


class GetDeviceHistoryQuery:
    """
    QUERY: Fetches device status history from Cold Storage.
    Supports 24h, 7d, 30d, 60d retention periods.
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
        days: int = 1,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> List[DeviceHistoryDTO]:
        """
        Execute query to get device history from Cold Storage.

        Args:
            equip_code: Equipment code
            days: Number of days to fetch (1=24h, 7, 30, 60)
            start_time: Optional explicit start time
            end_time: Optional explicit end time
        """
        # Calculate time range
        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time - timedelta(days=days)

        # Try cache
        cache_key = f"history_{equip_code}_{days}d"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        async with self._uow_factory() as uow:
            # Get history from Cold Storage
            periods = await uow.history.get_history(equip_code, start_time, end_time)

        # Convert to DTOs
        results = [
            DeviceHistoryDTO(
                equip_code=p.device_code,
                status_code=str(p.status_code),  # Convert to string
                timestamp=p.start_time,
                status_name=p.status_name,
                end_time=p.end_time,
            )
            for p in periods
        ]

        # Cache for 60 seconds
        await self._cache.set(cache_key, results, ttl=60)

        return results

    async def execute_24h(self, equip_code: str) -> List[DeviceHistoryDTO]:
        """Convenience method for 24h history."""
        return await self.execute(equip_code, days=1)

    async def execute_7d(self, equip_code: str) -> List[DeviceHistoryDTO]:
        """Convenience method for 7 day history."""
        return await self.execute(equip_code, days=7)

    async def execute_30d(self, equip_code: str) -> List[DeviceHistoryDTO]:
        """Convenience method for 30 day history."""
        return await self.execute(equip_code, days=30)

    async def execute_60d(self, equip_code: str) -> List[DeviceHistoryDTO]:
        """Convenience method for 60 day history."""
        return await self.execute(equip_code, days=60)
