"""
Device Queries (Hot Storage).
Read-only operations for current device state.
"""

from typing import List, Optional, Callable

from iFactory.application.common.dtos import DeviceStatusDTO
from iFactory.application.common.exceptions import ResourceNotFoundException
from iFactory.application.ports.cache import ICacheProvider
from iFactory.application.ports.uow import AbstractUnitOfWork


class GetAllDevicesStatusQuery:
    """
    QUERY: Fetches current status of all devices.
    """

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork], cache: ICacheProvider):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> List[DeviceStatusDTO]:
        # Caching strategy: Short TTL for liveliness
        cache_key = "all_devices_status_extended"
        cached = await self._cache.get(cache_key)

        if cached:
            results = cached
        else:
            async with self._uow_factory() as uow:
                # Use the new optimized snapshot method from repository
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
                    # Extended Data
                    name=device.name,
                    description=device.description,
                    material_batch=material.material_batch.value if material else None,
                    feeding_time=material.feeding_time if material else None,
                    input_count=0,  # Placeholder: Real count requires heavy history aggregation
                )
                results.append(dto)

            await self._cache.set(cache_key, results, ttl=1)

        if equipment_codes:
            return [d for d in results if d.equip_code in equipment_codes]
        return results


class GetLatestDeviceStatusQuery:
    """
    QUERY: Fetches current status of a single device.
    """

    def __init__(self, uow_factory: Callable[[], AbstractUnitOfWork], cache: ICacheProvider):
        self._uow_factory = uow_factory
        self._cache = cache

    async def execute(self, equip_code: str, theme: str = "light") -> Optional[DeviceStatusDTO]:
        cache_key = f"device_status_{equip_code}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        async with self._uow_factory() as uow:
            device = await uow.devices.get_by_code_string(equip_code)
            if not device:
                pass

        if not device:
            return None

        dto = DeviceStatusDTO(
            equip_code=device.equipment_code.value,
            status_code=str(device.current_status.value),
            status_name=device.current_status.name,
            last_update=device.last_updated_at,
            is_active=device.is_active,
            name=device.name,
            description=device.description,
        )

        await self._cache.set(cache_key, dto, ttl=1)
        return dto
