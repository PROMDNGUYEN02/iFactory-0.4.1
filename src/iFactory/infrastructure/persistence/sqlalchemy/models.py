"""
SQLAlchemy ORM Models.
Separated into Hot Storage (latest) and Cold Storage (history).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import String, DateTime, Boolean, Integer, ForeignKey, Index
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


# =============================================================================
# BASE CLASSES
# =============================================================================


class HotBase(DeclarativeBase):
    """Base class for Hot Storage models (latest state)."""

    pass


class ColdBase(DeclarativeBase):
    """Base class for Cold Storage models (history)."""

    pass


# Backward compatibility alias
Base = HotBase


# =============================================================================
# HOT STORAGE MODELS - Latest State
# =============================================================================


class DeviceModel(HotBase):
    """
    Latest device status snapshot.
    Hot Storage - frequently updated, fast reads.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    equip_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    def __repr__(self) -> str:
        return f"DeviceModel(code={self.equip_code!r}, status={self.equip_status})"


class LatestMaterialInputModel(HotBase):
    """
    Latest material input per device.
    Hot Storage - current feeding state.
    """

    __tablename__ = "latest_material_inputs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"LatestMaterialInput(code={self.equipment_code!r})"


# =============================================================================
# COLD STORAGE MODELS - History
# =============================================================================


class StatusPeriodModel(ColdBase):
    """
    Status period history for Gantt chart.
    Cold Storage - historical data, retention configurable.
    Supports: 24h (default), 7d, 30d, 60d retention.
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

    def __repr__(self) -> str:
        return f"StatusPeriodModel(device={self.device_id!r}, status={self.status})"


class MaterialInputHistoryModel(ColdBase):
    """
    Material input history.
    Cold Storage - feeding history for traceability.
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

    def __repr__(self) -> str:
        return f"MaterialInputHistory(code={self.equipment_code!r}, batch={self.material_batch!r})"


# Legacy alias for backward compatibility
MaterialInputModel = MaterialInputHistoryModel


__all__ = [
    "Base",
    "HotBase",
    "ColdBase",
    "DeviceModel",
    "LatestMaterialInputModel",
    "StatusPeriodModel",
    "MaterialInputHistoryModel",
    "MaterialInputModel",
]
