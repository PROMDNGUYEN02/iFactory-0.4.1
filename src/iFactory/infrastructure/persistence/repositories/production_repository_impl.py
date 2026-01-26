"""
SQLite implementation of the unified ProductionRepository.
"""

from __future__ import annotations
import logging
from typing import Optional, Sequence
from sqlalchemy import select, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

# Domain imports
from iFactory.domain.repositories import ProductionRepository
from iFactory.domain.value_objects import EquipmentCode, StatusPeriod, TimeRange, MaterialInput, Status

# Infrastructure imports
from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models import StatusHistory, LatestInput, InputHistory

__all__ = ["SqliteProductionRepository"]
logger = logging.getLogger(__name__)


class SqliteProductionRepository(ProductionRepository):
    """
    Unified repository handling both Status Periods and Material Inputs.
    Uses Hot Engine for latest states and Cold Engine for history.
    """

    __slots__ = ("_hot", "_cold")

    def __init__(self, hot_engine: AsyncSQLiteEngine, cold_engine: AsyncSQLiteEngine):
        self._hot = hot_engine
        self._cold = cold_engine

    # --- Status Management ---

    async def get_latest_status(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        stmt = select(StatusHistory).where(StatusHistory.equip_code == code.value).order_by(desc(StatusHistory.start_time)).limit(1)
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return self._map_status_period(row) if row else None

    async def get_status_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]:
        stmt = (
            select(StatusHistory)
            .where(StatusHistory.equip_code == code.value)
            .where(StatusHistory.start_time >= window.start)
            .where(StatusHistory.start_time <= window.end)
            .order_by(desc(StatusHistory.start_time))
        )
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            return [self._map_status_period(r) for r in result.scalars().all()]

    async def save_status_period(self, period: StatusPeriod) -> None:
        values = {
            "equip_code": period.equipment_code.value,
            "equip_status": period.status.name,  # mapped to standard name
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
            await session.commit()

    # --- Material Input Management ---

    async def get_latest_input(self, code: EquipmentCode) -> Optional[MaterialInput]:
        stmt = select(LatestInput).where(LatestInput.equip_code == code.value)
        async with self._hot.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            return MaterialInput.create(row.equip_code, row.material_batch, row.feeding_time) if row else None

    async def get_input_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]:
        stmt = (
            select(InputHistory)
            .where(InputHistory.equip_code == code.value)
            .where(InputHistory.feeding_time >= window.start)
            .where(InputHistory.feeding_time <= window.end)
            .order_by(desc(InputHistory.feeding_time))
        )
        async with self._cold.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [MaterialInput.create(r.equip_code, r.material_batch, r.feeding_time) for r in rows]

    async def save_material_input(self, record: MaterialInput) -> None:
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

        async with self._hot.session() as hot_session:
            await hot_session.execute(latest_stmt)
            await hot_session.commit()

        async with self._cold.session() as cold_session:
            await cold_session.execute(history_stmt)
            await cold_session.commit()

    # --- Internal Mappers ---
    def _map_status_period(self, model: StatusHistory) -> StatusPeriod:
        """Inline mapper to avoid circular dependencies in repo."""
        return StatusPeriod.create(code=model.equip_code, raw_status=model.equip_status, start=model.start_time, end=model.end_time)
