from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.remote_data_source import IRemoteDataSource
from iFactory.application.mappers.remote_record_mapper import to_device_entity
from iFactory.application.exceptions import ApplicationException


class SyncDeviceStatusUseCase:
    def __init__(self, uow: IUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str) -> bool:
        raw_data = await self._remote_api.fetch_device_status(equip_code)
        if not raw_data:
            return False

        device_entity = to_device_entity(raw_data)
        if not device_entity:
            return False

        async with self._uow:
            await self._uow.devices.save(device_entity)
            await self._uow.commit()

        return True
