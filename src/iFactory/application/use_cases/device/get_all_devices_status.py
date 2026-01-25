"""
Get All Devices Status Use Case.
Thuộc Tầng Application - Chỉ điều phối luồng dữ liệu, không có logic UI.
"""

from typing import List, Optional

from iFactory.application.dtos.device_dtos import DeviceStatusDTO
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.cache_provider import ICacheProvider
from iFactory.application.mappers.device_mapper import to_device_status_dto


class GetAllDevicesStatusUseCase:
    """Use case to fetch the current status of all devices with caching."""

    def __init__(self, uow: IUnitOfWork, cache: ICacheProvider):
        self._uow = uow
        self._cache = cache

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> List[DeviceStatusDTO]:
        cache_key = "all_devices_status"

        # 1. Check Cache first
        cached_status = await self._cache.get(cache_key)
        if cached_status:
            # Lọc từ cache nếu có yêu cầu
            if equipment_codes:
                return [s for s in cached_status if s.equip_code in equipment_codes]
            return cached_status

        # 2. Fetch from Database via Unit of Work
        async with self._uow:
            devices = await self._uow.devices.get_all()

        # 3. Map Domain Entities to Application DTOs
        results = [to_device_status_dto(device) for device in devices]

        # 4. Save to Cache for 60 seconds (Lưu toàn bộ danh sách)
        await self._cache.set(cache_key, results, ttl=60)

        # 5. Filter data from DB if needed
        if equipment_codes:
            results = [s for s in results if s.equip_code in equipment_codes]

        return results
