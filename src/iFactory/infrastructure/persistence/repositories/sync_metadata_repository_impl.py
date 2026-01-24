"""
SQLite implementation of SyncMetadataRepository.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Dict
from sqlalchemy import select, delete
from iFactory.domain import SyncMetadataRepository, SyncMetadata
from iFactory.infrastructure.database import AsyncSQLiteEngine, SyncMeta

__all__ = ["SqliteSyncMetadataRepository"]
logger = logging.getLogger(__name__)


class SqliteSyncMetadataRepository(SyncMetadataRepository):
    """
    SQLite implementation of SyncMetadataRepository.

    Uses SyncMeta table in hot store to track sync timestamps.
    """

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

    async def dispose(self) -> None:
        pass

    async def get(self, table_name: str) -> Optional[SyncMetadata]:
        stmt = select(SyncMeta).where(SyncMeta.table_name == table_name)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return SyncMetadata(
                    table_name=row.table_name,
                    last_sync=row.last_synced or datetime.min,
                    record_count=row.sync_count,
                    sync_status=row.sync_status or "idle",
                    error_message=row.error_message,
                )
            return None

    async def get_last_sync(self, table_name: str) -> Optional[datetime]:
        stmt = select(SyncMeta.last_synced).where(SyncMeta.table_name == table_name)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return result.scalar()

    async def get_all(self) -> Dict[str, SyncMetadata]:
        stmt = select(SyncMeta)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return {
                row.table_name: SyncMetadata(
                    table_name=row.table_name,
                    last_sync=row.last_synced or datetime.min,
                    record_count=row.sync_count,
                    sync_status=row.sync_status or "idle",
                    error_message=row.error_message,
                )
                for row in rows
            }

    async def has_synced(self, table_name: str) -> bool:
        metadata = await self.get(table_name)
        return metadata is not None and metadata.last_sync > datetime.min

    async def save(self, metadata: SyncMetadata) -> None:
        async with self._engine.session() as session:
            result = await session.execute(
                select(SyncMeta).where(SyncMeta.table_name == metadata.table_name)
            )
            row = result.scalar_one_or_none()
            if row:
                row.last_synced = metadata.last_sync
                row.sync_count = metadata.record_count
                row.sync_status = metadata.sync_status
                row.error_message = metadata.error_message
            else:
                session.add(
                    SyncMeta(
                        table_name=metadata.table_name,
                        last_synced=metadata.last_sync,
                        sync_count=metadata.record_count,
                        sync_status=metadata.sync_status,
                        error_message=metadata.error_message,
                    )
                )

    async def set_last_sync(self, table_name: str, timestamp: datetime) -> None:
        async with self._engine.session() as session:
            result = await session.execute(
                select(SyncMeta).where(SyncMeta.table_name == table_name)
            )
            row = result.scalar_one_or_none()
            if row:
                row.last_synced = timestamp
                row.sync_status = "success"
            else:
                session.add(
                    SyncMeta(
                        table_name=table_name,
                        last_synced=timestamp,
                        sync_status="success",
                    )
                )

    async def mark_sync_started(self, table_name: str) -> None:
        async with self._engine.session() as session:
            result = await session.execute(
                select(SyncMeta).where(SyncMeta.table_name == table_name)
            )
            row = result.scalar_one_or_none()
            if row:
                row.sync_status = "in_progress"
                row.error_message = None
            else:
                session.add(SyncMeta(table_name=table_name, sync_status="in_progress"))

    async def mark_sync_completed(self, table_name: str, record_count: int = 0) -> None:
        async with self._engine.session() as session:
            result = await session.execute(
                select(SyncMeta).where(SyncMeta.table_name == table_name)
            )
            row = result.scalar_one_or_none()
            now = datetime.now()
            if row:
                row.last_synced = now
                row.sync_count += record_count
                row.sync_status = "success"
                row.error_message = None
            else:
                session.add(
                    SyncMeta(
                        table_name=table_name,
                        last_synced=now,
                        sync_count=record_count,
                        sync_status="success",
                    )
                )

    async def mark_sync_failed(self, table_name: str, error_message: str) -> None:
        async with self._engine.session() as session:
            result = await session.execute(
                select(SyncMeta).where(SyncMeta.table_name == table_name)
            )
            row = result.scalar_one_or_none()
            if row:
                row.sync_status = "failed"
                row.error_message = error_message[:500]
            else:
                session.add(
                    SyncMeta(
                        table_name=table_name,
                        sync_status="failed",
                        error_message=error_message[:500],
                    )
                )

    async def delete(self, table_name: str) -> bool:
        stmt = delete(SyncMeta).where(SyncMeta.table_name == table_name)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return result.rowcount > 0

    async def reset_all(self) -> None:
        stmt = delete(SyncMeta)
        async with self._engine.session() as session:
            await session.execute(stmt)
