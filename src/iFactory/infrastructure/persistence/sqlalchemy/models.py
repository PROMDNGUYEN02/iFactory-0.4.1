# src/iFactory/infrastructure/persistence/sqlalchemy/models.py
"""
Infrastructure: SQLAlchemy Models.

Features:
- Automatic timestamps (created_at, updated_at)
- Soft delete support
- Proper indexing for performance
- Type-safe column definitions
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    DateTime,
    Index,
    Integer,
    String,
    event,
    func,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    declared_attr,
)


# ============================================================================
# Base Classes
# ============================================================================


class TimestampMixin:
    """Mixin for automatic timestamp management."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        server_default=func.now(),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
        onupdate=datetime.now,
        server_default=func.now(),
    )


class SoftDeleteMixin:
    """Mixin for soft delete support."""

    is_deleted: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    def soft_delete(self) -> None:
        """Mark record as deleted without removing from database."""
        self.is_deleted = True
        self.deleted_at = datetime.now()

    def restore(self) -> None:
        """Restore a soft-deleted record."""
        self.is_deleted = False
        self.deleted_at = None


class StorageBase(DeclarativeBase):
    """Base class for all storage models."""

    # Optional: Add common methods to all models
    def to_dict(self) -> dict:
        """Convert model to dictionary."""
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


# Legacy compatibility aliases
HotBase = StorageBase
ColdBase = StorageBase
Base = StorageBase


# ============================================================================
# Helper Functions
# ============================================================================


def generate_uuid() -> str:
    """Generate a new UUID string."""
    return str(uuid4())


# ============================================================================
# Models
# ============================================================================


class StatusHistoryModel(StorageBase, TimestampMixin):
    """
    Historical status logs.

    Primary table for storing device status history.
    Records each status period with start and optional end time.
    """

    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        default=generate_uuid,
    )

    equip_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    equip_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    equip_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        index=True,
    )

    start_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Additional metadata
    reason_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    duration_seconds: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    __table_args__ = (
        # Composite index for common queries
        Index("ix_status_history_code_time", "equip_code", "start_time"),
        Index("ix_status_history_code_status", "equip_code", "equip_status"),
        Index("ix_status_history_start_time", "start_time"),
        # Covering index for time range queries
        Index(
            "ix_status_history_range",
            "equip_code",
            "start_time",
            "end_time",
        ),
    )

    def calculate_duration(self) -> Optional[int]:
        """Calculate duration in seconds."""
        if self.end_time and self.start_time:
            return int((self.end_time - self.start_time).total_seconds())
        return None

    def __repr__(self) -> str:
        return f"StatusHistoryModel(id={self.id!r}, " f"code={self.equip_code!r}, " f"status={self.equip_status}, " f"start={self.start_time})"


class MaterialInputHistoryModel(StorageBase, TimestampMixin):
    """Historical material feedings log."""

    __tablename__ = "material_input_history"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        default=generate_uuid,
    )

    equipment_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )

    material_batch: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )

    feeding_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        index=True,
    )

    quantity: Mapped[Optional[float]] = mapped_column(
        nullable=True,
    )

    unit: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_material_history_code_time", "equipment_code", "feeding_time"),
        Index("ix_material_history_batch", "material_batch"),
    )

    def __repr__(self) -> str:
        return f"MaterialInputHistoryModel(id={self.id!r}, " f"code={self.equipment_code!r}, " f"batch={self.material_batch!r})"


class DeviceModel(StorageBase, TimestampMixin, SoftDeleteMixin):
    """
    Device cache for offline mode.

    Stores the latest known state of each device.
    """

    __tablename__ = "devices_cache"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        default=generate_uuid,
    )

    equip_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    equip_name: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )

    equip_status: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        index=True,
    )

    reason_code: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        index=True,
    )

    last_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    # Sync metadata
    last_sync: Mapped[Optional[datetime]] = mapped_column(
        DateTime,
        nullable=True,
    )

    sync_source: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_devices_active", "is_active", "is_deleted"),
        Index("ix_devices_status", "equip_status"),
    )

    def __repr__(self) -> str:
        return f"DeviceModel(code={self.equip_code!r}, " f"status={self.equip_status}, " f"active={self.is_active})"


class LatestMaterialInputModel(StorageBase, TimestampMixin):
    """
    Latest material batch feeding cache.

    Stores only the most recent material input per device
    for quick dashboard lookups.
    """

    __tablename__ = "latest_material_inputs"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
        default=generate_uuid,
    )

    equipment_code: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        unique=True,
        index=True,
    )

    material_batch: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    feeding_time: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"LatestMaterialInputModel(code={self.equipment_code!r}, " f"batch={self.material_batch!r})"


# ============================================================================
# Event Listeners
# ============================================================================


@event.listens_for(StatusHistoryModel, "before_insert")
@event.listens_for(StatusHistoryModel, "before_update")
def calculate_status_duration(mapper, connection, target: StatusHistoryModel):
    """Auto-calculate duration when end_time is set."""
    if target.end_time and target.start_time:
        target.duration_seconds = int((target.end_time - target.start_time).total_seconds())


# ============================================================================
# Aliases for backward compatibility
# ============================================================================

MaterialInputModel = MaterialInputHistoryModel


__all__ = [
    # Base classes
    "StorageBase",
    "Base",
    "HotBase",
    "ColdBase",
    "TimestampMixin",
    "SoftDeleteMixin",
    # Models
    "StatusHistoryModel",
    "MaterialInputHistoryModel",
    "MaterialInputModel",
    "DeviceModel",
    "LatestMaterialInputModel",
    # Utilities
    "generate_uuid",
]
