from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional

from ..entities.sync_metadata import SyncMetadata


class SyncMetadataRepository(ABC):
    @abstractmethod
    async def get(self, table_name: str) -> Optional[SyncMetadata]:
        pass

    @abstractmethod
    async def get_all(self) -> Dict[str, SyncMetadata]:
        pass

    @abstractmethod
    async def save(self, metadata: SyncMetadata) -> None:
        pass

    @abstractmethod
    async def mark_sync_completed(self, table_name: str, record_count: int = 0) -> None:
        pass

    @abstractmethod
    async def mark_sync_failed(self, table_name: str, error_message: str) -> None:
        pass
