"""
Cold store ORM models - Historical data tables.

These tables store historical records for reporting and
Gantt chart generation. Data is archived from hot store.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String,
    DateTime,
    Integer,
    Float,
    UniqueConstraint,
    Index,
    CheckConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, validates
from ..base import ColdBase

__all__ = ["StatusHistory", "InputHistory"]


class StatusHistory(ColdBase):
    """
    Status history with time periods.

    Each record represents a period during which a device
    had a specific status. Used for Gantt charts.
    """

    __tablename__ = "history_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    equip_status: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    __table_args__ = (
        UniqueConstraint("equip_code", "start_time", name="uix_status_history"),
        Index("ix_history_range", "equip_code", "start_time", "end_time"),
        Index("ix_history_status", "equip_status"),
        CheckConstraint("duration >= 0", name="ck_duration_positive"),
    )

    @validates("duration")
    def validate_duration(self, key: str, value: float) -> float:
        """Ensure duration is non-negative."""
        return max(0.0, value or 0.0)

    @validates("equip_code")
    def validate_equip_code(self, key: str, value: str) -> str:
        """Normalize equipment code to uppercase."""
        return value.strip().upper() if value else value

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration / 60.0

    @property
    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.duration / 3600.0

    def calculate_duration(self) -> float:
        """Calculate and update duration from time range."""
        if self.start_time and self.end_time:
            self.duration = (self.end_time - self.start_time).total_seconds()
        return self.duration


class InputHistory(ColdBase):
    """
    Material input history records.

    Tracks all material batches fed to each equipment over time.
    """

    __tablename__ = "history_input"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    __table_args__ = (
        UniqueConstraint("equip_code", "feeding_time", name="uix_input_history"),
        Index("ix_input_batch", "material_batch"),
    )

    @validates("equip_code")
    def validate_equip_code(self, key: str, value: str) -> str:
        """Normalize equipment code to uppercase."""
        return value.strip().upper() if value else value
