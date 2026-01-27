"""
SQLAlchemy ORM Models.
Pure database representation. No business logic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import Column, String, DateTime, Boolean, Integer, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class DeviceModel(Base):
    """
    ORM Model representing the 'devices' table.
    Maps to Domain Device entity.
    """

    __tablename__ = "devices"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True, index=True)
    equip_status: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_update: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    status_periods: Mapped[List["StatusPeriodModel"]] = relationship(
        "StatusPeriodModel",
        back_populates="device",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"DeviceModel(id={self.id!r}, " f"code={self.equip_code!r}, " f"status={self.equip_status})"


class StatusPeriodModel(Base):
    """
    ORM Model representing the 'status_periods' table.
    Maps to Domain StatusPeriod value object.
    """

    __tablename__ = "status_periods"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    device_id: Mapped[str] = mapped_column(String(50), ForeignKey("devices.id"), nullable=False, index=True)
    status: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    device: Mapped["DeviceModel"] = relationship("DeviceModel", back_populates="status_periods")

    def __repr__(self) -> str:
        return f"StatusPeriodModel(id={self.id!r}, " f"device={self.device_id!r}, " f"status={self.status})"


class MaterialInputModel(Base):
    """
    ORM Model representing the 'material_inputs' table.
    """

    __tablename__ = "material_inputs"

    id: Mapped[str] = mapped_column(String(50), primary_key=True)
    equipment_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    def __repr__(self) -> str:
        return f"MaterialInputModel(code={self.equipment_code!r}, " f"batch={self.material_batch!r})"
