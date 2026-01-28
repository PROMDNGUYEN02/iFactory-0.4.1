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
        uow_factory: Callable,
        cache: ICacheProvider,
    ):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[DeviceStatusDTO]:
        cache_key = "all_devices_status"

        cached_status = await self._cache.get(cache_key)
        if cached_status:
            if equipment_codes:
                return [s for s in cached_status if s.equip_code in equipment_codes]
            return cached_status

        async with self._uow_factory() as uow:
            devices = await uow.devices.get_all()

        results = [
            DeviceStatusDTO(
                equip_code=d.equipment_code.value,
                status_code=str(d.current_status.value),
                status_name=d.current_status.name,
                last_update=d.last_updated_at,
                is_active=d.is_active,
            )
            for d in devices
        ]

        await self._cache.set(cache_key, results, ttl=60)

        if equipment_codes:
            results = [s for s in results if s.equip_code in equipment_codes]

        return results
