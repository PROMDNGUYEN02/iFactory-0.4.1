from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class SyncMetadata:
    table_name: str
    last_sync: datetime
    record_count: int = 0
    status: str = "success"
    error_message: Optional[str] = None

    def mark_success(self, count: int, time: datetime | None = None) -> SyncMetadata:
        return SyncMetadata(table_name=self.table_name, last_sync=time or datetime.now(), record_count=count, status="success")

    def mark_failure(self, error: str, time: datetime | None = None) -> SyncMetadata:
        return SyncMetadata(table_name=self.table_name, last_sync=time or datetime.now(), record_count=0, status="failed", error_message=error)
