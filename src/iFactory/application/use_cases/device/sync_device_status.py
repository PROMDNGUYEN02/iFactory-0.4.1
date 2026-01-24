"""Sync device status use case."""

import logging
from typing import Optional, Sequence

from iFactory.application.interfaces import RemoteDataSource, UnitOfWork
from iFactory.application.mappers import RemoteRecordMapper

logger = logging.getLogger(__name__)


class SyncDeviceStatusUseCase:
    """
    Use case: Synchronize device statuses from remote data source.
    Command use case using UnitOfWork.
    """

    __slots__ = ("_remote_source", "_uow_factory")

    def __init__(
        self,
        remote_data_source: RemoteDataSource,
        unit_of_work_factory: callable,
    ):
        self._remote_source = remote_data_source
        self._uow_factory = unit_of_work_factory

    async def execute(self, equipment_codes: Optional[Sequence[str]] = None) -> int:
        try:
            records = await self._remote_source.fetch_latest_status(equipment_codes)

            if not records:
                logger.info("[SyncDeviceStatus] No records to sync")
                return 0

            synced_count = 0

            async with self._uow_factory() as uow:
                for record in records:
                    device = RemoteRecordMapper.to_device(record)
                    if device is None:
                        continue

                    await uow.devices.save(device)
                    synced_count += 1

                await uow.commit()

            logger.info(f"[SyncDeviceStatus] Synced {synced_count} devices")
            return synced_count

        except ConnectionError as e:
            logger.error(f"[SyncDeviceStatus] Remote connection failed (Offline?): {e}")
            return 0
        except Exception as e:
            logger.exception(f"[SyncDeviceStatus] Unexpected error during sync: {e}")
            return 0
