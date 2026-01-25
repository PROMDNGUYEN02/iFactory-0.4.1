"""
Infrastructure Sync Service.
"""

import logging
from dataclasses import dataclass, field
from typing import List

from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.remote_data_source import IRemoteDataSource
from iFactory.application.mappers.remote_record_mapper import to_device_entity

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    equip_code: str
    success: bool
    message: str = ""
    records_processed: int = 0


@dataclass
class SyncAllResult:
    total: int = 0
    success: int = 0
    failed: int = 0
    results: List[SyncResult] = field(default_factory=list)


class SyncService:
    # Đổi tên tham số từ 'uow' thành 'db' để khớp với tham số của AppContainer
    def __init__(self, db: IUnitOfWork, remote_source: IRemoteDataSource):
        self._uow = db
        self._remote_source = remote_source

    async def sync_device(self, equip_code: str) -> SyncResult:
        try:
            raw_data = await self._remote_source.fetch_device_status(equip_code)
            if not raw_data:
                return SyncResult(equip_code, False, "No data from remote API")

            device = to_device_entity(raw_data)
            if not device:
                return SyncResult(equip_code, False, "Mapping failed")

            async with self._uow:
                await self._uow.devices.save(device)
                await self._uow.commit()

            return SyncResult(equip_code, True, "Success", 1)
        except Exception as e:
            logger.error(f"Sync failed for {equip_code}: {e}")
            return SyncResult(equip_code, False, str(e))
