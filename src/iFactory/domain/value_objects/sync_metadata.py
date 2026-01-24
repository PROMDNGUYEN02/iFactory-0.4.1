from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

__all__ = ["SyncMetadata"]


@dataclass(frozen=True, slots=True)
class SyncMetadata:
    """Entity: Metadata đồng bộ dữ liệu."""

    table_name: str
    last_sync: datetime
    record_count: int = 0
    sync_status: str = "success"
    error_message: Optional[str] = None

    @classmethod
    def create(cls, table_name: str, last_sync: Optional[datetime] = None) -> "SyncMetadata":
        """Create new sync metadata."""
        return cls(table_name=table_name, last_sync=last_sync or datetime.now())

    def with_success(self, record_count: int = 0, sync_time: Optional[datetime] = None) -> "SyncMetadata":
        """Create updated metadata after successful sync."""
        return SyncMetadata(
            table_name=self.table_name,
            last_sync=sync_time or datetime.now(),
            record_count=record_count,
            sync_status="success",
            error_message=None,
        )

    def with_failure(self, error_message: str, sync_time: Optional[datetime] = None) -> "SyncMetadata":
        """Create updated metadata after failed sync."""
        return SyncMetadata(
            table_name=self.table_name,
            last_sync=sync_time or datetime.now(),
            record_count=0,
            sync_status="failed",
            error_message=error_message,
        )
