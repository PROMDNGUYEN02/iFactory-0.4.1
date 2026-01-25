"""
Infrastructure Sync Service.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import List, Optional

from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.remote_data_source import IRemoteDataSource
from iFactory.application.mappers.remote_record_mapper import to_device_entity

logger = logging.getLogger(__name__)


@dataclass
class SyncResult:
    success: bool
    hot_count: int = 0
    cold_count: int = 0
    skipped_count: int = 0
    message: str = ""


@dataclass
class SyncAllResult:
    status: SyncResult = field(default_factory=lambda: SyncResult(True))
    input: SyncResult = field(default_factory=lambda: SyncResult(True))
    history: SyncResult = field(default_factory=lambda: SyncResult(True))
    input_history: SyncResult = field(default_factory=lambda: SyncResult(True))


class SyncService:
    def __init__(self, db: IUnitOfWork, data_source: IRemoteDataSource, history_interval: int = 300):
        self._uow = db
        self._remote_source = data_source
        self._history_interval = history_interval
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("[SyncService] Initialized")

    async def get_device_codes(self) -> List[str]:
        """Lấy danh sách mã thiết bị từ local DB."""
        async with self._uow:
            devices = await self._uow.devices.get_all()
            return [d.code for d in devices]

    async def sync_status_hot(self, codes: Optional[List[str]] = None) -> SyncResult:
        if not codes:
            codes = await self.get_device_codes()

        count = 0
        try:
            for code in codes:
                raw = await self._remote_source.fetch_device_status(code)
                if raw:
                    device = to_device_entity(raw)
                    async with self._uow:
                        await self._uow.devices.save(device)
                        await self._uow.commit()
                    count += 1
            return SyncResult(True, hot_count=count)
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            return SyncResult(False, message=str(e))

    async def sync_input_hot(self, codes: List[str]) -> SyncResult:
        return SyncResult(True)

    async def sync_history_cold(self, codes: List[str], hours: int = 24, force: bool = False) -> SyncResult:
        return SyncResult(True)

    async def sync_input_history_cold(self, codes: List[str], hours: int = 24) -> SyncResult:
        return SyncResult(True)

    async def sync_all(self, codes: List[str], include_history: bool = True) -> SyncAllResult:
        s = await self.sync_status_hot(codes)
        return SyncAllResult(status=s)
