from iFactory.application.ports.unit_of_work import IUnitOfWork
from iFactory.application.ports.remote_data_source import IRemoteDataSource
from iFactory.domain.entities.device import Device


class SyncDeviceStatusCommand:
    """
    COMMAND: Syncs a single device status by equipment code.
    Returns: bool (success)
    """

    def __init__(self, uow: IUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str) -> bool:
        raw_data = await self._remote_api.fetch_device_status(equip_code)
        if not raw_data:
            return False

        device_entity = Device.create(
            code=raw_data.get("equip_code"), raw_status=raw_data.get("equip_status", "0"), last_update=raw_data.get("last_update")
        )

        async with self._uow as uow:
            await uow.devices.save(device_entity)
            await uow.commit()

        return True
