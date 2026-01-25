"""
SQLite implementation of InputRepository.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Sequence, Dict
from sqlalchemy import select, delete, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from iFactory.domain import InputRepository, MaterialInput, TimeRange
from iFactory.domain.value_objects import EquipmentCode
from iFactory.infrastructure.database import AsyncSQLiteEngine, LatestInput, InputHistory

__all__ = ["SqliteInputRepository"]
logger = logging.getLogger(__name__)


class SqliteInputRepository(InputRepository):
    BATCH_SIZE = 500
    __slots__ = ("_hot_engine", "_cold_engine", "_initialized")

    def __init__(self, hot_engine: AsyncSQLiteEngine, cold_engine: AsyncSQLiteEngine):
        self._hot_engine = hot_engine
        self._cold_engine = cold_engine
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        async with self._hot_engine.engine.begin() as conn:
            await conn.run_sync(LatestInput.metadata.create_all)
        async with self._cold_engine.engine.begin() as conn:
            await conn.run_sync(InputHistory.metadata.create_all)
        self._initialized = True

    async def get_latest(self, code: EquipmentCode) -> Optional[MaterialInput]:
        stmt = select(LatestInput).where(LatestInput.equip_code == code.value)
        async with self._hot_engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return MaterialInput.create(row.equip_code, row.material_batch, row.feeding_time)
            return None

    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]:
        stmt = (
            select(InputHistory)
            .where(InputHistory.equip_code == code.value)
            .where(InputHistory.feeding_time >= window.start)
            .where(InputHistory.feeding_time <= window.end)
            .order_by(desc(InputHistory.feeding_time))
        )
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [MaterialInput.create(r.equip_code, r.material_batch, r.feeding_time) for r in rows]

    async def save(self, record: MaterialInput) -> None:
        """Lưu đồng thời vào bảng Latest và bảng History."""
        values = {
            "equip_code": record.equipment_code.value,
            "material_batch": record.material_batch,
            "feeding_time": record.feeding_time,
        }

        # 1. Update Hot Store (Latest)
        latest_stmt = sqlite_insert(LatestInput).values(**values)
        latest_stmt = latest_stmt.on_conflict_do_update(
            index_elements=["equip_code"],
            set_={"material_batch": latest_stmt.excluded.material_batch, "feeding_time": latest_stmt.excluded.feeding_time},
        )

        # 2. Update Cold Store (History)
        history_stmt = sqlite_insert(InputHistory).values(**values)
        history_stmt = history_stmt.on_conflict_do_update(
            index_elements=["equip_code", "feeding_time"], set_={"material_batch": history_stmt.excluded.material_batch}
        )

        async with self._hot_engine.session() as hot_session:
            await hot_session.execute(latest_stmt)
            await hot_session.commit()

        async with self._cold_engine.session() as cold_session:
            await cold_session.execute(history_stmt)
            await cold_session.commit()

    async def delete_history_before(self, cutoff: datetime) -> int:
        stmt = delete(InputHistory).where(InputHistory.feeding_time < cutoff)
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
