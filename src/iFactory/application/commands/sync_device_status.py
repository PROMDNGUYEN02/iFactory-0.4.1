"""
Application Command: Sync Single Device Status.
"""

import logging
from typing import Optional

from iFactory.application.ports.unit_of_work import AbstractUnitOfWork
from iFactory.application.ports.remote_data_source import IRemoteDataSource
from iFactory.domain.entities.device import Device

logger = logging.getLogger(__name__)


class SyncDeviceStatusCommand:
    """
    COMMAND: Syncs a single device status by equipment code.
    Returns: bool (success)
    """

    def __init__(self, uow: AbstractUnitOfWork, remote_api: IRemoteDataSource):
        self._uow = uow
        self._remote_api = remote_api

    async def execute(self, equip_code: str) -> bool:
        try:
            raw_data = await self._remote_api.fetch_device_status(equip_code)
            if not raw_data:
                return False

            device_entity = Device.create(
                code=raw_data.get("equip_code"),
                raw_status=raw_data.get("equip_status", "0"),
                last_update=raw_data.get("last_update"),
            )

            async with self._uow as uow:
                # Use save() which handles upsert via merge
                await uow.devices.save(device_entity)
                await uow.commit()

            return True

        except Exception as e:
            logger.error(f"Failed to sync device {equip_code}: {e}")
            return False
