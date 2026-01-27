from typing import List, Optional

from iFactory.application.dto.device_dto import DeviceStatusDTO

# [FIXED] Đổi IUnitOfWork thành AbstractUnitOfWork
from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.ports.cache import ICacheProvider


class GetAllDevicesStatusQuery:
    """
    QUERY: Fetches current status of all devices (with 60s cache).
    """

    # [FIXED] Cập nhật type hint
    def __init__(self, uow: AbstractUnitOfWork, cache: ICacheProvider):
        self._uow = uow
        self._cache = cache

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> List[DeviceStatusDTO]:
        cache_key = "all_devices_status"

        cached_status = await self._cache.get(cache_key)
        if cached_status:
            if equipment_codes:
                return [s for s in cached_status if s.equip_code in equipment_codes]
            return cached_status

        # Query bypasses full repository hydration for read optimization if possible,
        # but here we map from Domain to DTO.
        async with self._uow as uow:
            devices = await uow.devices.get_all()

        results = [
            DeviceStatusDTO(equip_code=d.code, status_code=d.status, status_name=d.status_name, last_update=d.last_update, is_active=d.is_active)
            for d in devices
        ]

        await self._cache.set(cache_key, results, ttl=60)

        if equipment_codes:
            results = [s for s in results if s.equip_code in equipment_codes]

        return results
