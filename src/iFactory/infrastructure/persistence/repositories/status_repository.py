from __future__ import annotations
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, delete, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from iFactory.domain import StatusRepository, TimeRange, StatusPeriod
from iFactory.domain.value_objects import EquipmentCode
from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models.cold_models import StatusHistory
from ..mappers.status_mapper import StatusPeriodMapper


class SqliteStatusRepository(StatusRepository):
    def __init__(self, hot_engine: AsyncSQLiteEngine, cold_engine: AsyncSQLiteEngine):
        self._hot = hot_engine
        self._cold = cold_engine

    async def get_latest(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        stmt = select(StatusHistory).where(StatusHistory.equip_code == code.value).order_by(desc(StatusHistory.start_time)).limit(1)
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return StatusPeriodMapper.to_entity(row) if row else None

    async def save_period(self, period: StatusPeriod) -> None:
        values = {
            "equip_code": period.equipment_code.value,
            "equip_status": period.status.code,
            "start_time": period.time_range.start,
            "end_time": period.time_range.end,
            "duration": period.duration_seconds,
        }
        stmt = sqlite_insert(StatusHistory).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code", "start_time"],
            set_={"equip_status": stmt.excluded.equip_status, "end_time": stmt.excluded.end_time, "duration": stmt.excluded.duration},
        )
        async with self._cold.session() as session:
            await session.execute(stmt)
