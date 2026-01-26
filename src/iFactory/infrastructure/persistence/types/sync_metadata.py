from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass(frozen=True, slots=True)
class SyncMetadata:
    """Infrastructure DTO for tracking database synchronization states."""

    table_name: str
    last_sync: datetime
    record_count: int = 0
    status: str = "success"
    error_message: Optional[str] = None
