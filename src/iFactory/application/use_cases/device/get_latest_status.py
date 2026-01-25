from iFactory.application.dtos.device_dtos import DeviceStatusDTO
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.cache_provider import ICacheProvider
from iFactory.application.mappers.device_mapper import to_device_status_dto
from iFactory.application.exceptions import ResourceNotFoundException


class GetLatestDeviceStatusUseCase:
    def __init__(self, uow: IUnitOfWork, cache: ICacheProvider):
        self._uow = uow
        self._cache = cache

    async def execute(self, equip_code: str) -> DeviceStatusDTO:
        cache_key = f"status_{equip_code}"
        cached = await self._cache.get(cache_key)
        if cached:
            return cached

        async with self._uow:
            device = await self._uow.devices.get_by_equipment_code(equip_code)

        if not device:
            raise ResourceNotFoundException("Device", equip_code)

        result = to_device_status_dto(device)
        await self._cache.set(cache_key, result, ttl=30)
        return result
