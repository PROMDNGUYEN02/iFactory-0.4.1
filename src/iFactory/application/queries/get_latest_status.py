"""
Get Latest Device Status Query.
"""

from typing import Optional

from iFactory.application.dto.device_dto import DeviceStatusDTO
from iFactory.application.ports.unit_of_work import IUnitOfWork
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.exceptions.application_exceptions import ResourceNotFoundException


class GetLatestDeviceStatusQuery:
    """
    QUERY: Fetches the latest status of a single device.
    Uses caching for read optimization.
    """

    def __init__(self, uow: IUnitOfWork, cache: ICacheProvider):
        self._uow = uow
        self._cache = cache

    async def execute(self, equip_code: str, theme: str = "light") -> Optional[DeviceStatusDTO]:
        """
        Executes the query.
        Note: The 'theme' parameter is ignored at the application level as UI
        styling is strictly handled in the Presentation layer.
        """
        cache_key = f"device_status_{equip_code}"

        # 1. Check Cache
        cached_dto = await self._cache.get(cache_key)
        if cached_dto:
            return cached_dto

        # 2. Fetch from Database via Unit of Work
        async with self._uow as uow:
            device = await uow.devices.get_by_equipment_code(equip_code)

        if not device:
            raise ResourceNotFoundException(f"Device not found: {equip_code}")

        # 3. Map Domain Entity to Application DTO
        dto = DeviceStatusDTO(
            equip_code=device.code,
            status_code=device.status,
            status_name=device.status_name,
            last_update=device.last_update,
            is_active=device.is_active,
        )

        # 4. Update Cache (TTL 60s)
        await self._cache.set(cache_key, dto, ttl=60)

        return dto
