from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import String, DateTime, Integer, Index, CheckConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, validates
from ..base import HotBase


class DeviceStateModel(HotBase):
    __tablename__ = "latest_status"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    equip_status: Mapped[str] = mapped_column(String(2), nullable=False, default="0")
    last_update: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    start_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (
        Index("ix_latest_status_update", "equip_code", "last_update"),
        CheckConstraint("length(equip_code) > 0", name="ck_status_code_not_empty"),
    )

    @validates("equip_status")
    def validate_status(self, key: str, value: str) -> str:
        if not value:
            return "0"
        try:
            v = int(str(value).strip())
            return str(v) if 0 <= v <= 5 else "0"
        except ValueError:
            return "0"

    @validates("equip_code")
    def validate_equip_code(self, key: str, value: str) -> str:
        if not value:
            raise ValueError("Equipment code cannot be empty")
        return value.strip().upper()


class DeviceInputModel(HotBase):
    __tablename__ = "latest_input"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    equip_code: Mapped[str] = mapped_column(String(30), unique=True, index=True, nullable=False)
    material_batch: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    feeding_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.now)
    __table_args__ = (Index("ix_latest_input_time", "equip_code", "feeding_time"),)


class SyncMetadataModel(HotBase):
    __tablename__ = "sync_meta"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    table_name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sync_count: Mapped[int] = mapped_column(Integer, default=0)
    sync_status: Mapped[str] = mapped_column(String(20), default="idle")
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
