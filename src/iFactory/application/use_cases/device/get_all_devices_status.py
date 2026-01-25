"""
Get All Devices Status Use Case.
Thuộc Tầng Application - Chỉ điều phối luồng dữ liệu, không có logic UI.
"""

from typing import List

from iFactory.application.dtos.device_dtos import DeviceStatusDTO
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.cache_provider import ICacheProvider
from iFactory.application.mappers.device_mapper import to_device_status_dto


class GetAllDevicesStatusUseCase:
    """Use case to fetch the current status of all devices with caching."""

    def __init__(self, uow: IUnitOfWork, cache: ICacheProvider):
        self._uow = uow
        self._cache = cache

    async def execute(self) -> List[DeviceStatusDTO]:
        # 1. Check Cache first
        cached_status = await self._cache.get("all_devices_status")
        if cached_status:
            return cached_status

        # 2. Fetch from Database via Unit of Work
        async with self._uow:
            devices = await self._uow.devices.get_all()

        # 3. Map Domain Entities to Application DTOs
        results = [to_device_status_dto(device) for device in devices]

        # 4. Save to Cache for 60 seconds
        await self._cache.set("all_devices_status", results, ttl=60)

        return results
