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
    """
    SQLite implementation of InputRepository.

    Uses:
        - Hot store (LatestInput) for current input
        - Cold store (InputHistory) for historical data
    """

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

    async def dispose(self) -> None:
        pass

    async def get_latest(self, code: EquipmentCode) -> Optional[MaterialInput]:
        code_str = code.value
        stmt = select(LatestInput).where(LatestInput.equip_code == code_str)
        async with self._hot_engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                # FIXED: Use Factory Method for Domain Entity
                return MaterialInput.create(
                    equip_code=row.equip_code,
                    material_batch=row.material_batch,
                    feeding_time=row.feeding_time,
                )
            return None

    async def get_all_latest(self, codes: Optional[Sequence[EquipmentCode]] = None) -> Sequence[MaterialInput]:
        stmt = select(LatestInput)
        if codes:
            code_strs = [c.value for c in codes]
            stmt = stmt.where(LatestInput.equip_code.in_(code_strs))
        async with self._hot_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            # FIXED: Use Factory Method
            return [
                MaterialInput.create(
                    equip_code=r.equip_code,
                    material_batch=r.material_batch,
                    feeding_time=r.feeding_time,
                )
                for r in rows
            ]

    async def get_history_for_codes(self, codes: Sequence[EquipmentCode], time_range: TimeRange) -> Dict[str, Sequence[MaterialInput]]:
        """
        Get input history for multiple devices.

        Args:
            codes: Equipment code Value Objects
            time_range: Time range to query

        Returns:
            Dictionary mapping equipment code to input sequences
        """
        code_strs = [c.value for c in codes]
        result: Dict[str, list] = {code: [] for code in code_strs}

        if not code_strs:
            return result

        stmt = (
            select(InputHistory)
            .where(InputHistory.equip_code.in_(code_strs))
            .where(InputHistory.feeding_time >= time_range.start)
            .where(InputHistory.feeding_time <= time_range.end)
            .order_by(InputHistory.equip_code, desc(InputHistory.feeding_time))
        )

        async with self._cold_engine.session() as session:
            db_result = await session.execute(stmt)
            for row in db_result.scalars().all():
                code = row.equip_code
                if code not in result:
                    result[code] = []
                # FIXED: Use Factory Method
                result[code].append(
                    MaterialInput.create(
                        equip_code=code,
                        material_batch=row.material_batch,
                        feeding_time=row.feeding_time,
                    )
                )

        return result

    async def get_history(self, code: EquipmentCode, time_range: TimeRange) -> Sequence[MaterialInput]:
        code_str = code.value
        stmt = (
            select(InputHistory)
            .where(InputHistory.equip_code == code_str)
            .where(InputHistory.feeding_time >= time_range.start)
            .where(InputHistory.feeding_time <= time_range.end)
            .order_by(desc(InputHistory.feeding_time))
        )
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            # FIXED: Use Factory Method
            return [
                MaterialInput.create(
                    equip_code=r.equip_code,
                    material_batch=r.material_batch,
                    feeding_time=r.feeding_time,
                )
                for r in rows
            ]

    async def save_latest(self, input_record: MaterialInput) -> None:
        values = {
            "equip_code": input_record.equipment_code.value,  # FIXED: Access value through equipment_code
            "material_batch": input_record.material_batch,
            "feeding_time": input_record.feeding_time,
        }
        stmt = sqlite_insert(LatestInput).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code"],
            set_={
                "material_batch": stmt.excluded.material_batch,
                "feeding_time": stmt.excluded.feeding_time,
            },
        )
        async with self._hot_engine.session() as session:
            await session.execute(stmt)

    async def save_latest_many(self, inputs: Sequence[MaterialInput]) -> int:
        if not inputs:
            return 0
        values = [
            {
                "equip_code": i.equipment_code.value,  # FIXED: Access value
                "material_batch": i.material_batch,
                "feeding_time": i.feeding_time,
            }
            for i in inputs
        ]
        stmt = sqlite_insert(LatestInput).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code"],
            set_={
                "material_batch": stmt.excluded.material_batch,
                "feeding_time": stmt.excluded.feeding_time,
            },
        )
        async with self._hot_engine.session() as session:
            await session.execute(stmt)
        return len(inputs)

    async def save_to_history(self, input_record: MaterialInput) -> None:
        values = {
            "equip_code": input_record.equipment_code.value,  # FIXED: Access value
            "material_batch": input_record.material_batch,
            "feeding_time": input_record.feeding_time,
        }
        stmt = sqlite_insert(InputHistory).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code", "feeding_time"],
            set_={"material_batch": stmt.excluded.material_batch},
        )
        async with self._cold_engine.session() as session:
            await session.execute(stmt)

    async def save_many_to_history(self, inputs: Sequence[MaterialInput]) -> int:
        if not inputs:
            return 0
        values = [
            {
                "equip_code": i.equipment_code.value,  # FIXED: Access value
                "material_batch": i.material_batch,
                "feeding_time": i.feeding_time,
            }
            for i in inputs
        ]
        total = 0
        for i in range(0, len(values), self.BATCH_SIZE):
            batch = values[i : i + self.BATCH_SIZE]
            stmt = sqlite_insert(InputHistory).values(batch)
            stmt = stmt.on_conflict_do_update(
                index_elements=["equip_code", "feeding_time"],
                set_={"material_batch": stmt.excluded.material_batch},
            )
            async with self._cold_engine.session() as session:
                await session.execute(stmt)
            total += len(batch)
        return total

    async def delete_history_before(self, cutoff: datetime) -> int:
        stmt = delete(InputHistory).where(InputHistory.feeding_time < cutoff)
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            return result.rowcount
