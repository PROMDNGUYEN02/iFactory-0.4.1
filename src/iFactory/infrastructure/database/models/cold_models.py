from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Float, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..base import ColdBase


class StatusHistoryModel(ColdBase):
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
        CheckConstraint("duration >= 0", name="ck_duration_positive"),
    )


class InputHistoryModel(ColdBase):
    __tablename__ = "history_input"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False)
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    __table_args__ = (UniqueConstraint("equip_code", "feeding_time", name="uix_input_history"),)
