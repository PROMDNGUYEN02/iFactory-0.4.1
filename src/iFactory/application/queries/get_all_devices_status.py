"""
Get All Devices Status Query.
Uses Hot Storage for latest state.
"""

from typing import List, Optional, Callable

from iFactory.application.dto.device_dto import DeviceStatusDTO
from iFactory.application.ports.cache import ICacheProvider


class GetAllDevicesStatusQuery:
    """
    QUERY: Fetches current status of all devices from Hot Storage with caching.
    """

    def __init__(
        self,
        uow_factory: Callable,  # Returns HotStorageUnitOfWork
        cache: ICacheProvider,
    ):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[DeviceStatusDTO]:
        cache_key = "all_devices_status"

        # Try cache first
        cached_status = await self._cache.get(cache_key)
        if cached_status:
            if equipment_codes:
                return [s for s in cached_status if s.equip_code in equipment_codes]
            return cached_status

        # Fetch from Hot Storage
        async with self._uow_factory() as uow:
            devices = await uow.devices.get_all()

        results = [
            DeviceStatusDTO(
                equip_code=d.code,
                status_code=str(d.status),  # Convert to string
                status_name=d.status_name,
                last_update=d.last_update,
                is_active=d.is_active,
            )
            for d in devices
        ]

        # Cache for 60 seconds
        await self._cache.set(cache_key, results, ttl=60)

        if equipment_codes:
            results = [s for s in results if s.equip_code in equipment_codes]

        return results
