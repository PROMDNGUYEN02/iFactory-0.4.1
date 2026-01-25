"""
SQLite implementation of StatusRepository.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Sequence, Dict
from sqlalchemy import select, delete, func, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from iFactory.domain import StatusRepository, DeviceHistory, TimeRange, StatusPeriod
from iFactory.domain.value_objects import EquipmentCode, Status
from iFactory.infrastructure.database import AsyncSQLiteEngine, LatestStatus, StatusHistory
from ..mappers import StatusPeriodOrmMapper

__all__ = ["SqliteStatusRepository"]
logger = logging.getLogger(__name__)


class SqliteStatusRepository(StatusRepository):
    """
    SQLite implementation of StatusRepository.

    Uses:
        - Hot store (LatestStatus) for current status
        - Cold store (StatusHistory) for historical data
    """

    BATCH_SIZE = 500
    __slots__ = ("_hot_engine", "_cold_engine", "_initialized")

    def __init__(self, hot_engine: AsyncSQLiteEngine, cold_engine: AsyncSQLiteEngine):
        """
        Initialize repository.

        Args:
            hot_engine: SQLite engine for hot store
            cold_engine: SQLite engine for cold store
        """
        self._hot_engine = hot_engine
        self._cold_engine = cold_engine
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize repository."""
        if self._initialized:
            return
        async with self._hot_engine.engine.begin() as conn:
            await conn.run_sync(LatestStatus.metadata.create_all)
        async with self._cold_engine.engine.begin() as conn:
            await conn.run_sync(StatusHistory.metadata.create_all)
        self._initialized = True
        logger.debug("[StatusRepository] Initialized")

    async def dispose(self) -> None:
        """Clean up resources."""
        pass

    async def get_latest(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        """Get latest status period for a device."""
        stmt = select(StatusHistory).where(StatusHistory.equip_code == code.value).order_by(desc(StatusHistory.start_time)).limit(1)
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return StatusPeriodOrmMapper.to_entity(row)
            return None

    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]:
        """Get status history for a device."""
        stmt = (
            select(StatusHistory)
            .where(StatusHistory.equip_code == code.value)
            .where(StatusHistory.start_time >= window.start)
            .where(StatusHistory.start_time <= window.end)
            .order_by(desc(StatusHistory.start_time))
        )
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return StatusPeriodOrmMapper.to_entities(rows)

    async def save_period(self, period: StatusPeriod) -> None:
        """Save status period to storage."""
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
            set_={
                "equip_status": stmt.excluded.equip_status,
                "end_time": stmt.excluded.end_time,
                "duration": stmt.excluded.duration,
            },
        )

        async with self._cold_engine.session() as session:
            await session.execute(stmt)
            await session.commit()

    async def save_latest(self, period: DeviceHistory) -> None:
        """Compatibility: Save/update latest status."""
        await self.save_period(period)

    async def save_to_history(self, period: DeviceHistory) -> None:
        """Compatibility: Archive status period to history."""
        await self.save_period(period)

    async def delete_history_before(self, cutoff: datetime) -> int:
        """Delete history records before cutoff."""
        stmt = delete(StatusHistory).where(StatusHistory.start_time < cutoff)
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return result.rowcount
