from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import select

from .sync_metadata_repository import SyncMetadataRepository
from ..types.sync_metadata import SyncMetadata
from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models import SyncMetadataModel


class SqliteSyncMetadataRepository(SyncMetadataRepository):
    def __init__(self, engine: AsyncSQLiteEngine):
        self._engine = engine

    async def get_by_table(self, table_name: str) -> Optional[SyncMetadata]:
        stmt = select(SyncMetadataModel).where(SyncMetadataModel.table_name == table_name)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if not row:
                return None
            return SyncMetadata(
                table_name=row.table_name,
                last_sync=row.last_synced or datetime.min,
                status=row.sync_status or "success",
                error_message=row.error_message,
            )

    async def save(self, metadata: SyncMetadata) -> None:
        async with self._engine.session() as session:
            result = await session.execute(select(SyncMetadataModel).where(SyncMetadataModel.table_name == metadata.table_name))
            row = result.scalar_one_or_none()
            if row:
                row.last_synced = metadata.last_sync
                row.sync_status = metadata.status
                row.error_message = metadata.error_message
            else:
                session.add(
                    SyncMetadataModel(
                        table_name=metadata.table_name,
                        last_synced=metadata.last_sync,
                        sync_status=metadata.status,
                        error_message=metadata.error_message,
                    )
                )
