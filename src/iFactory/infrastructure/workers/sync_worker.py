"""
Background Orchestration Worker.
Coordinates data flow from external boundaries to local persistence.
"""

import logging
from datetime import datetime
from typing import List

from iFactory.application.interfaces.remote_data_source import IRemoteDataSource
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.infrastructure.mappers.remote_mapper import RemoteDeviceMapper

logger = logging.getLogger(__name__)


class SyncWorker:
    """
    Imperative background worker to push data from external DB to Local UoW.
    Does not contain business logic. Delegates construction to the Mapper.
    """

    def __init__(self, data_source: IRemoteDataSource, uow: IUnitOfWork):
        self._remote_source = data_source
        self._uow = uow

    async def run_sync_job(self, target_codes: List[str]) -> None:
        """Fetch raw records, map to domain, persist via UoW."""
        logger.info(f"SyncWorker: Starting job for {len(target_codes)} devices...")

        try:
            now = datetime.now()
            raw_records = await self._remote_source.fetch_latest_status(target_codes)

            async with self._uow as uow:
                for raw in raw_records:
                    device = RemoteDeviceMapper.from_raw_record(raw, now)
                    await uow.devices.save(device)

                await uow.commit()

            logger.info(f"SyncWorker: Successfully synced {len(raw_records)} devices.")

        except Exception as e:
            logger.error(f"SyncWorker: Failed with error: {e}")
            raise
