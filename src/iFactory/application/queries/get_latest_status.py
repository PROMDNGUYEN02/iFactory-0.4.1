"""
Get Latest Device Status Query.
Uses Hot Storage for latest state.
"""

from typing import Optional, Callable

from iFactory.application.dto.device_dto import DeviceStatusDTO
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.exceptions.application_exceptions import ResourceNotFoundException


class GetLatestDeviceStatusQuery:
    """
    QUERY: Fetches the latest status of a single device from Hot Storage.
    Uses caching for read optimization.
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
        equip_code: str,
        theme: str = "light",
    ) -> Optional[DeviceStatusDTO]:
        """
        Executes the query.
        """
        cache_key = f"device_status_{equip_code}"

        cached_dto = await self._cache.get(cache_key)
        if cached_dto:
            return cached_dto

        async with self._uow_factory() as uow:
            device = await uow.devices.get_by_code_string(equip_code)

        if not device:
            raise ResourceNotFoundException(f"Device not found: {equip_code}")

        dto = DeviceStatusDTO(
            equip_code=device.equipment_code.value,
            status_code=str(device.current_status.value),
            status_name=device.current_status.name,
            last_update=device.last_updated_at,
            is_active=device.is_active,
        )

        await self._cache.set(cache_key, dto, ttl=60)

        return dto
