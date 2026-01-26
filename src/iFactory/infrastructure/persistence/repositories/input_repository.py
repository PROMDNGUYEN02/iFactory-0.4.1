from __future__ import annotations
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from iFactory.domain.repositories.input_repository import InputRepository
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models.hot_models import DeviceInputModel
from iFactory.infrastructure.database.models.cold_models import InputHistoryModel
from iFactory.infrastructure.persistence.mappers.entity_mapper import EntityMapper


class SqliteInputRepository(InputRepository):
    def __init__(self, hot_engine: AsyncSQLiteEngine, cold_engine: AsyncSQLiteEngine):
        self._hot = hot_engine
        self._cold = cold_engine

    async def get_latest(self, code: EquipmentCode) -> Optional[MaterialInput]:
        stmt = select(DeviceInputModel).where(DeviceInputModel.equip_code == code.value)
        async with self._hot.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return EntityMapper.to_material_input_entity(row) if row else None

    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]:
        stmt = (
            select(InputHistoryModel)
            .where(InputHistoryModel.equip_code == code.value)
            .where(InputHistoryModel.feeding_time >= window.start)
            .where(InputHistoryModel.feeding_time <= window.end)
            .order_by(desc(InputHistoryModel.feeding_time))
        )
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            return [EntityMapper.to_material_input_entity(r) for r in result.scalars().all()]

    async def save(self, record: MaterialInput) -> None:
        values = {
            "equip_code": record.equipment_code.value,
            "material_batch": record.batch_number,
            "feeding_time": record.timestamp or datetime.now(),
        }

        hot_stmt = sqlite_insert(DeviceInputModel).values(**values)
        hot_stmt = hot_stmt.on_conflict_do_update(
            index_elements=["equip_code"], set_={"material_batch": hot_stmt.excluded.material_batch, "feeding_time": hot_stmt.excluded.feeding_time}
        )

        cold_stmt = sqlite_insert(InputHistoryModel).values(**values)
        cold_stmt = cold_stmt.on_conflict_do_update(
            index_elements=["equip_code", "feeding_time"], set_={"material_batch": cold_stmt.excluded.material_batch}
        )

        async with self._hot.session() as session:
            await session.execute(hot_stmt)
        async with self._cold.session() as session:
            await session.execute(cold_stmt)
