"""
SQLAlchemy ORM Models.
Separated into Hot Storage (latest state) and Cold Storage (history).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, Integer, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class HotBase(DeclarativeBase):
    """Base class for Hot Storage models (latest state)."""

    pass


class ColdBase(DeclarativeBase):
    """Base class for Cold Storage models (history)."""

    pass


# =============================================================================
# HOT STORAGE - Latest State
# =============================================================================


class DeviceModel(HotBase):
    """
    Latest device status snapshot.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    equip_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)


class LatestMaterialInputModel(HotBase):
    """
    Latest material input per device.
    """

    __tablename__ = "latest_material_inputs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)


# =============================================================================
# COLD STORAGE - History
# =============================================================================


class StatusPeriodModel(ColdBase):
    """
    Status period history for timeline analysis.
    """

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
    """
    Historical log of material inputs.
    """

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
