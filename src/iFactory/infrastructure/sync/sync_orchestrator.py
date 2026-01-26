import logging
from typing import List, Optional
from iFactory.application.interfaces.remote_data_source import IRemoteDataSource
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.infrastructure.mappers.device_mapper import DeviceMapper
from iFactory.domain.entities.device import Device

logger = logging.getLogger(__name__)


class SyncOrchestrator:
    """
    Coordinates data movement between the remote data source and the local Unit of Work.
    Relies on Application mappers and Domain entities.
    """

    def __init__(self, data_source: IRemoteDataSource, uow: IUnitOfWork):
        self._remote_source = data_source
        self._uow = uow

    async def sync_all_devices(self, target_codes: List[str]) -> None:
        """
        Fetches the latest status for target codes from remote and saves to local DB.
        """
        logger.info(f"Starting sync for {len(target_codes)} devices...")

        try:
            raw_records = await self._remote_source.fetch_latest_status(target_codes)

            async with self._uow as uow:
                for raw in raw_records:
                    # Map raw dict to Domain Entity
                    device = Device.create(code=raw["equip_code"], raw_status=raw["equip_status"], last_update=raw["last_update"])
                    await uow.devices.save(device)
                await uow.commit()

            logger.info(f"Successfully synced {len(raw_records)} devices.")

        except Exception as e:
            logger.error(f"Sync failed: {e}")
            raise
