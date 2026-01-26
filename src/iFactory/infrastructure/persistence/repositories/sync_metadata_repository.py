from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from ..types.sync_metadata import SyncMetadata


class SyncMetadataRepository(ABC):
    """Interface for persisting synchronization state."""

    @abstractmethod
    async def get_by_table(self, table_name: str) -> Optional[SyncMetadata]: ...

    @abstractmethod
    async def save(self, metadata: SyncMetadata) -> None: ...
