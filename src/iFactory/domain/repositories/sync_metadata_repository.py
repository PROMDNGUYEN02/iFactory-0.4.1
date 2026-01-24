"""
Sync metadata repository interface - Contract for sync tracking.

This interface defines how application tracks synchronization
state for incremental data sync.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Dict

from ..value_objects.sync_metadata import SyncMetadata

__all__ = ["SyncMetadataRepository"]


class SyncMetadataRepository(ABC):
    """
    Abstract repository for sync metadata persistence.

    Tracks synchronization timestamps and status for each
    data source/table to enable incremental sync.

    Contract:
        - All methods are async (non-blocking for Qt GUI)
        - Returns Domain entities (not DTOs, not ORM models)
    """

    # ====== QUERIES ======

    @abstractmethod
    async def get(
        self,
        table_name: str
    ) -> Optional[SyncMetadata]:
        """
        Get sync metadata for a table.

        Args:
            table_name: Table/source identifier

        Returns:
            Sync metadata or None if never synced
        """
        pass

    @abstractmethod
    async def get_last_sync(
        self,
        table_name: str
    ) -> Optional[datetime]:
        """
        Get last sync timestamp for a table.

        Args:
            table_name: Table/source identifier

        Returns:
            Last sync timestamp or None if never synced
        """
        pass

    @abstractmethod
    async def get_all(self) -> Dict[str, SyncMetadata]:
        """
        Get all sync metadata.

        Returns:
            Dictionary mapping table name to metadata
        """
        pass

    @abstractmethod
    async def has_synced(
        self,
        table_name: str
    ) -> bool:
        """
        Check if table has ever been synced.

        Args:
            table_name: Table/source identifier

        Returns:
            True if table has been synced at least once
        """
        pass

    # ====== COMMANDS ======

    @abstractmethod
    async def save(
        self,
        metadata: SyncMetadata
    ) -> None:
        """
        Save sync metadata.

        Args:
            metadata: Sync metadata to save

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def set_last_sync(
        self,
        table_name: str,
        timestamp: datetime
    ) -> None:
        """
        Set last sync timestamp for a table.

        Convenience method for simple timestamp updates.

        Args:
            table_name: Table/source identifier
            timestamp: Sync timestamp

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def mark_sync_started(
        self,
        table_name: str
    ) -> None:
        """
        Mark sync as in progress.

        Args:
            table_name: Table/source identifier

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def mark_sync_completed(
        self,
        table_name: str,
        record_count: int = 0
    ) -> None:
        """
        Mark sync as successfully completed.

        Args:
            table_name: Table/source identifier
            record_count: Number of records synced

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def mark_sync_failed(
        self,
        table: str,
        error_message: str
    ) -> None:
        """
        Mark sync as failed.

        Args:
            table_name: Table/source identifier
            error_message: Error description

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def delete(
        self,
        table_name: str
    ) -> bool:
        """
        Delete sync metadata for a table.

        Args:
            table_name: Table/source identifier

        Returns:
            True if metadata was deleted

        Raises:
            RepositoryError: If delete fails
        """
        pass

    @abstractmethod
    async def reset_all(self) -> None:
        """
        Reset all sync metadata (force full re-sync).

        Raises:
            RepositoryError: If reset fails
        """
        pass
