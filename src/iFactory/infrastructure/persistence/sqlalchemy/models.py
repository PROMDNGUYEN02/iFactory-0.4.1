"""
Infrastructure: SQLAlchemy Models.
Simplified: Single base for storage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, Integer, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class StorageBase(DeclarativeBase):
    """Single base for all storage models."""

    pass


# Legacy compatibility aliases
HotBase = StorageBase
ColdBase = StorageBase
Base = StorageBase


class StatusHistoryModel(StorageBase):
    """
    Historical status logs.
    This is the primary table for storing device status history.
    """

    __tablename__ = "status_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    equip_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    equip_status: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_status_history_code_time", "equip_code", "start_time"),
        Index("ix_status_history_start_time", "start_time"),
    )


class MaterialInputHistoryModel(StorageBase):
    """Historical material feedings log."""

    __tablename__ = "material_input_history"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)

    __table_args__ = (
        Index("ix_material_history_code_time", "equipment_code", "feeding_time"),
        Index("ix_material_history_recorded", "recorded_at"),
    )


class DeviceModel(StorageBase):
    """Device cache (optional - for offline mode)."""

    __tablename__ = "devices_cache"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    equip_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    equip_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LatestMaterialInputModel(StorageBase):
    """Latest material batch feeding cache."""

    __tablename__ = "latest_material_inputs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# Aliases
MaterialInputModel = MaterialInputHistoryModel
