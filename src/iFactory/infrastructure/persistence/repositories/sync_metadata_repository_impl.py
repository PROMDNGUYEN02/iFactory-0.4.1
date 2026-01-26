"""
SQLite implementation of the Sync Metadata Repository.
Tracks the last sync time and status of synchronization operations.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models.hot_models import SyncMetadataModel
from iFactory.infrastructure.persistence.types.sync_metadata import SyncMetadata
from .sync_metadata_repository import SyncMetadataRepository

__all__ = ["SqliteSyncMetadataRepository"]


class SqliteSyncMetadataRepository(SyncMetadataRepository):
    """
    SQLite implementation for persisting synchronization metadata.
    Uses the Hot Engine since this is real-time operational data.
    """

    __slots__ = ("_engine",)

    def __init__(self, engine: AsyncSQLiteEngine):
        self._engine = engine

    async def get_by_table(self, table_name: str) -> Optional[SyncMetadata]:
        stmt = select(SyncMetadataModel).where(SyncMetadataModel.table_name == table_name)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if not model:
                return None
            return SyncMetadata(
                table_name=model.table_name,
                last_sync=model.last_synced,
                record_count=model.sync_count,
                status=model.sync_status,
                error_message=model.error_message,
            )

    async def save(self, metadata: SyncMetadata) -> None:
        values = {
            "table_name": metadata.table_name,
            "last_synced": metadata.last_sync or datetime.now(),
            "sync_count": metadata.record_count,
            "sync_status": metadata.status,
            "error_message": metadata.error_message,
        }

        # Upsert: Insert if new, update if exists based on 'table_name'
        stmt = sqlite_insert(SyncMetadataModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["table_name"],
            set_={
                "last_synced": stmt.excluded.last_synced,
                "sync_count": stmt.excluded.sync_count,
                "sync_status": stmt.excluded.sync_status,
                "error_message": stmt.excluded.error_message,
            },
        )

        async with self._engine.session() as session:
            await session.execute(stmt)
