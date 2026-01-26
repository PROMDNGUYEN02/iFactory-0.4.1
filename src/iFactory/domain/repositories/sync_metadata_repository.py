from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional
from ..value_objects.sync_metadata import SyncMetadata


class SyncMetadataRepository(ABC):
    @abstractmethod
    async def get_by_table(self, table_name: str) -> Optional[SyncMetadata]: ...

    @abstractmethod
    async def save(self, metadata: SyncMetadata) -> None: ...
