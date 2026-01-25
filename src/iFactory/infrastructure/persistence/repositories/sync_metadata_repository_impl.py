"""
SQLite implementation of SyncMetadataRepository.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy import select

from iFactory.domain import SyncMetadataRepository, SyncMetadata
from iFactory.infrastructure.database import AsyncSQLiteEngine, SyncMeta

__all__ = ["SqliteSyncMetadataRepository"]
logger = logging.getLogger(__name__)


class SqliteSyncMetadataRepository(SyncMetadataRepository):
    __slots__ = ("_engine", "_initialized")

    def __init__(self, engine: AsyncSQLiteEngine):
        self._engine = engine
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._engine.engine.begin() as conn:
            await conn.run_sync(SyncMeta.metadata.create_all)
        self._initialized = True

    async def get_by_table(self, table_name: str) -> Optional[SyncMetadata]:
        stmt = select(SyncMeta).where(SyncMeta.table_name == table_name)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None

            return SyncMetadata(
                table_name=row.table_name,
                last_sync=row.last_synced or datetime.min,
                record_count=row.sync_count or 0,
                status=row.sync_status or "success",
                error_message=row.error_message,
            )

    async def save(self, metadata: SyncMetadata) -> None:
        async with self._engine.session() as session:
            result = await session.execute(select(SyncMeta).where(SyncMeta.table_name == metadata.table_name))
            row = result.scalar_one_or_none()
            if row:
                row.last_synced = metadata.last_sync
                row.sync_count = metadata.record_count
                row.sync_status = metadata.status
                row.error_message = metadata.error_message
            else:
                session.add(
                    SyncMeta(
                        table_name=metadata.table_name,
                        last_synced=metadata.last_sync,
                        sync_count=metadata.record_count,
                        sync_status=metadata.status,
                        error_message=metadata.error_message,
                    )
                )
            await session.commit()
