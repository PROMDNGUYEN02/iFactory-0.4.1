"""
Get Latest Device Status Use Case.
Thuộc Tầng Application - Trả về trạng thái hiện tại của một thiết bị cụ thể.
"""

from typing import Optional

from iFactory.application.dtos.device_dtos import DeviceStatusDTO
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.cache_provider import ICacheProvider
from iFactory.application.mappers.device_mapper import to_device_status_dto
from iFactory.application.exceptions import ResourceNotFoundException


class GetLatestDeviceStatusUseCase:
    """Use case to fetch the latest status of a single device."""

    def __init__(self, uow: IUnitOfWork, cache: ICacheProvider):
        self._uow = uow
        self._cache = cache

    async def execute(self, equip_code: str) -> DeviceStatusDTO:
        cache_key = f"device_status_{equip_code}"

        # 1. Check Cache
        cached_status = await self._cache.get(cache_key)
        if cached_status:
            return cached_status

        # 2. Fetch from DB
        async with self._uow:
            device = await self._uow.devices.get_by_equipment_code(equip_code)

        if not device:
            raise ResourceNotFoundException("Device", equip_code)

        # 3. Map to DTO
        result = to_device_status_dto(device)

        # 4. Update Cache
        await self._cache.set(cache_key, result, ttl=30)

        return result
