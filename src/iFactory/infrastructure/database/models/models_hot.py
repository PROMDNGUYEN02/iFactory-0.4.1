"""
Hot store ORM models - Latest state tables.

These tables store the current state of each device and are
updated frequently during sync operations.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates
from ..base import HotBase

__all__ = ["LatestStatus", "LatestInput", "SyncMeta"]


class LatestStatus(HotBase):
    """
    Latest status per device.

    Stores the most recent status for each equipment code.
    Updated via sync from MSSQL.
    """

    __tablename__ = "latest_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(
        String(30), unique=True, index=True, nullable=False
    )
    equip_status: Mapped[str] = mapped_column(String(2), nullable=False, default="0")
    last_update: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    __table_args__ = (
        Index("ix_latest_status_update", "equip_code", "last_update"),
        CheckConstraint("length(equip_code) > 0", name="ck_status_code_not_empty"),
    )

    @validates("equip_status")
    def validate_status(self, key: str, value: str) -> str:
        """Normalize status to single digit (0-5)."""
        if not value:
            return "0"
        try:
            v = int(str(value).strip())
            return str(v) if 0 <= v <= 5 else "0"
        except ValueError:
            return "0"

    @validates("equip_code")
    def validate_equip_code(self, key: str, value: str) -> str:
        """Normalize equipment code to uppercase."""
        if not value:
            raise ValueError("Equipment code cannot be empty")
        return value.strip().upper()


class LatestInput(HotBase):
    """
    Latest material input per device.

    Stores the most recent material batch fed to each equipment.
    """

    __tablename__ = "latest_input"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(
        String(30), unique=True, index=True, nullable=False
    )
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    feeding_time: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, default=datetime.now
    )
    __table_args__ = (Index("ix_latest_input_time", "equip_code", "feeding_time"),)

    @validates("equip_code")
    def validate_equip_code(self, key: str, value: str) -> str:
        """Normalize equipment code to uppercase."""
        if not value:
            raise ValueError("Equipment code cannot be empty")
        return value.strip().upper()


class SyncMeta(HotBase):
    """
    Synchronization metadata tracking.

    Tracks the last sync time for each data source to enable
    incremental synchronization.
    """

    __tablename__ = "sync_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sync_count: Mapped[int] = mapped_column(Integer, default=0)
    sync_status: Mapped[str] = mapped_column(String(20), default="idle")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    __table_args__ = (Index("ix_sync_meta_table", "table_name"),)

    def mark_started(self) -> None:
        """Mark sync as started."""
        self.sync_status = "in_progress"
        self.error_message = None

    def mark_completed(self, count: int = 0) -> None:
        """Mark sync as completed."""
        self.last_synced = datetime.now()
        self.sync_count += count
        self.sync_status = "success"
        self.error_message = None

    def mark_failed(self, error: str) -> None:
        """Mark sync as failed."""
        self.sync_status = "failed"
        self.error_message = error[:500] if error else None
