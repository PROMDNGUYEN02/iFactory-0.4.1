from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from iFactory.domain.repositories.status_repository import StatusRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models import StatusHistoryModel
from iFactory.infrastructure.persistence.mappers.entity_mapper import EntityMapper


class SqliteStatusRepository(StatusRepository):
    def __init__(self, hot_engine: AsyncSQLiteEngine, cold_engine: AsyncSQLiteEngine):
        self._hot = hot_engine
        self._cold = cold_engine

    async def get_latest(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        stmt = select(StatusHistoryModel).where(StatusHistoryModel.equip_code == code.value).order_by(desc(StatusHistoryModel.start_time)).limit(1)
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return EntityMapper.to_status_period_entity(row) if row else None

    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]:
        stmt = (
            select(StatusHistoryModel)
            .where(StatusHistoryModel.equip_code == code.value)
            .where(StatusHistoryModel.start_time >= window.start)
            .where(StatusHistoryModel.start_time <= window.end)
            .order_by(desc(StatusHistoryModel.start_time))
        )
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            return [EntityMapper.to_status_period_entity(r) for r in result.scalars().all()]

    async def save_period(self, period: StatusPeriod) -> None:
        values = {
            "equip_code": period.equipment_code.value,
            "equip_status": period.status.code,
            "start_time": period.time_range.start,
            "end_time": period.time_range.end,
            "duration": period.duration_seconds,
        }
        stmt = sqlite_insert(StatusHistoryModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code", "start_time"],
            set_={"equip_status": stmt.excluded.equip_status, "end_time": stmt.excluded.end_time, "duration": stmt.excluded.duration},
        )
        async with self._cold.session() as session:
            await session.execute(stmt)
