import logging
from typing import List, Optional

from iFactory.domain.entities.device import Device
from iFactory.application.ports.unit_of_work import IUnitOfWork
from iFactory.application.ports.remote_data_source import IRemoteDataSource

logger = logging.getLogger(__name__)


class SyncAllDevicesCommand:
    """
    COMMAND: Fetches raw device statuses and persists them transactionally.
    Returns: int (number of devices updated)
    """

    def __init__(self, remote_source: IRemoteDataSource, uow: IUnitOfWork):
        self._remote_source = remote_source
        self._uow = uow

    async def execute(self, equipment_codes: Optional[List[str]] = None) -> int:
        logger.info("[SyncAllDevicesCommand] Starting synchronization...")

        remote_records = await self._remote_source.fetch_latest_status(equipment_codes)
        if not remote_records:
            return 0

        devices: List[Device] = []
        for record in remote_records:
            try:
                # Domain handles validation upon creation
                device = Device.create(
                    code=str(record.get("equip_code")), raw_status=str(record.get("equip_status", "0")), last_update=record.get("last_update")
                )
                devices.append(device)
            except Exception as e:
                logger.warning(f"[SyncAllDevicesCommand] Skipped invalid record: {e}")

        if not devices:
            return 0

        async with self._uow as uow:
            count = await uow.devices.save_many(devices)
            await uow.commit()

        logger.info(f"[SyncAllDevicesCommand] Synced {count} devices.")
        return count
