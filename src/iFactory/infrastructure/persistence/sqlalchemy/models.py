"""
Infrastructure: SQLAlchemy Models.
Declarative definitions for Hot and Cold storage tables.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, Integer, Index, BigInteger
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


# --- Base Classes ---


class HotBase(DeclarativeBase):
    """Base for Hot Storage (Latest State)."""

    pass


class ColdBase(DeclarativeBase):
    """Base for Cold Storage (History)."""

    pass


# Compatibility Alias (defaults to HotBase for generic uses)
Base = HotBase


# --- Hot Storage Models (Current State) ---


class DeviceModel(HotBase):
    """Latest snapshot of device state."""

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    equip_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    equip_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_code: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class LatestMaterialInputModel(HotBase):
    """Latest material batch feeding (Cache/Hot)."""

    __tablename__ = "latest_material_inputs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# --- Cold Storage Models (History) ---


class StatusPeriodModel(ColdBase):
    """Historical status periods."""

    __tablename__ = "status_periods"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_status_periods_device_time", "device_id", "start_time"),
        Index("ix_status_periods_start_time", "start_time"),
    )


class MaterialInputHistoryModel(ColdBase):
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


# Alias for backward compatibility
MaterialInputModel = MaterialInputHistoryModel
