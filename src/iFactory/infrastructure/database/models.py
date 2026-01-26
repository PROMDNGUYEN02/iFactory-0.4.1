from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Float, Index, CheckConstraint, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, validates
from iFactory.infrastructure.database.base import HotBase, ColdBase


class DeviceStateModel(HotBase):
    __tablename__ = "latest_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    equip_status: Mapped[str] = mapped_column(String(2), nullable=False, default="0")
    last_update: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    is_active: Mapped[bool] = mapped_column(default=True)
    __table_args__ = (
        Index("ix_device_update", "equip_code", "last_update"),
        CheckConstraint("length(equip_code) > 0", name="ck_equip_code_valid"),
    )

    @validates("equip_code")
    def validate_code(self, key: str, value: str) -> str:
        if not value:
            raise ValueError("Code cannot be empty")
        return value.strip().upper()


class StatusHistoryModel(ColdBase):
    __tablename__ = "history_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    equip_status: Mapped[str] = mapped_column(String(10), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    duration: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    __table_args__ = (
        UniqueConstraint("equip_code", "start_time", name="uix_history_entry"),
        CheckConstraint("duration >= 0", name="ck_duration_non_negative"),
    )


class SyncMetadataModel(HotBase):
    __tablename__ = "sync_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), default="idle")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
