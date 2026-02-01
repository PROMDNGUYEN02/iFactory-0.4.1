"""
Device Queries - For offline mode fallback.
In Remote-First architecture, these are optional.
"""

from typing import List, Optional, Callable

from iFactory.application.common.dtos import DeviceStatusDTO
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.ports.uow import AbstractUnitOfWork


class GetAllDevicesStatusQuery:
    """
    QUERY: Fetches current status from local cache.
    Fallback for offline mode.
    """

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        cache: ICacheProvider,
    ):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[DeviceStatusDTO]:
        cache_key = "all_devices_status"
        cached = await self._cache.get(cache_key)

        if cached:
            results = cached
        else:
            async with self._uow_factory() as uow:
                if not uow.devices:
                    return []
                snapshot_rows = await uow.devices.get_dashboard_snapshot()

            results = []
            for device, material in snapshot_rows:
                if not device:
                    continue

                dto = DeviceStatusDTO(
                    equip_code=device.equipment_code.value,
                    status_code=str(device.current_status.value),
                    status_name=device.current_status.name,
                    last_update=device.last_updated_at,
                    is_active=device.is_active,
                    name=device.equip_name,
                    description=None,
                    material_batch=material.material_batch.value if material else None,
                    feeding_time=material.feeding_time if material else None,
                    input_count=0,
                )
                results.append(dto)

            await self._cache.set(cache_key, results, ttl=1)

        if equipment_codes:
            return [d for d in results if d.equip_code in equipment_codes]
        return results


class GetLatestDeviceStatusQuery:
    """QUERY: Fetches current status of a single device from cache."""

    def __init__(
        self,
        uow_factory: Callable[[], AbstractUnitOfWork],
        cache: ICacheProvider,
    ):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(self, equip_code: str) -> Optional[DeviceStatusDTO]:
        cache_key = f"device_status_{equip_code}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        async with self._uow_factory() as uow:
            if not uow.devices:
                return None
            device = await uow.devices.get_by_code_string(equip_code)

        if not device:
            return None

        dto = DeviceStatusDTO(
            equip_code=device.equipment_code.value,
            status_code=str(device.current_status.value),
            status_name=device.current_status.name,
            last_update=device.last_updated_at,
            is_active=device.is_active,
            name=device.equip_name,
            description=None,
        )

        await self._cache.set(cache_key, dto, ttl=1)
        return dto
