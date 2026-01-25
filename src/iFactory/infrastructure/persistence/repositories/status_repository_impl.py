"""
SQLite implementation of StatusRepository.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Sequence, Dict
from sqlalchemy import select, delete, func, desc
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from iFactory.domain import StatusRepository, DeviceHistory, TimeRange
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

    async def get_latest(self, code: str | EquipmentCode) -> Optional[DeviceHistory]:
        """Get latest status period for a device."""
        code_str = code.value if isinstance(code, EquipmentCode) else str(code)
        stmt = select(StatusHistory).where(StatusHistory.equip_code == code_str).order_by(desc(StatusHistory.start_time)).limit(1)
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return StatusPeriodOrmMapper.to_entity(row)
            return None

    async def get_all_latest(self, codes: Optional[Sequence[EquipmentCode]] = None) -> Sequence[DeviceHistory]:
        """Get latest status for all devices."""
        codes_list = [c.value if isinstance(c, EquipmentCode) else c for c in codes] if codes else []

        stmt = select(StatusHistory)
        if codes_list:
            stmt = stmt.where(StatusHistory.equip_code.in_(codes_list))
        stmt = stmt.order_by(StatusHistory.equip_code, desc(StatusHistory.start_time))

        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            latest_map = {}
            for row in rows:
                if row.equip_code not in latest_map:
                    latest_map[row.equip_code] = StatusPeriodOrmMapper.to_entity(row)

            if not codes_list:
                return list(latest_map.values())

            return [latest_map[code] for code in codes_list if code in latest_map]

    async def save_latest(self, period: DeviceHistory) -> None:
        """Save/update latest status."""
        await self.save_to_history(period)

    async def save_latest_many(self, periods: Sequence[DeviceHistory]) -> int:
        """Save/update latest status for multiple devices."""
        return await self.save_many_to_history(periods)

    async def get_history(self, code: EquipmentCode, time_range: TimeRange) -> Sequence[DeviceHistory]:
        """Get status history for a device."""
        code_str = code.value
        stmt = (
            select(StatusHistory)
            .where(StatusHistory.equip_code == code_str)
            .where(StatusHistory.start_time >= time_range.start)
            .where(StatusHistory.start_time <= time_range.end)
            .order_by(desc(StatusHistory.start_time))
        )
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return StatusPeriodOrmMapper.to_entities(rows)

    async def get_history_for_codes(self, codes: Sequence[EquipmentCode], time_range: TimeRange) -> Dict[str, Sequence[DeviceHistory]]:
        """Get status history for multiple devices."""
        code_strs = [c.value for c in codes]
        result: Dict[str, list] = {code: [] for code in code_strs}
        stmt = (
            select(StatusHistory)
            .where(StatusHistory.equip_code.in_(code_strs))
            .where(StatusHistory.start_time >= time_range.start)
            .where(StatusHistory.start_time <= time_range.end)
            .order_by(StatusHistory.equip_code, desc(StatusHistory.start_time))
        )
        async with self._cold_engine.session() as session:
            rows = await session.execute(stmt)
            for row in rows.scalars().all():
                period = StatusPeriodOrmMapper.to_entity(row)
                result[period.code].append(period)
        return result

    async def save_to_history(self, period: DeviceHistory) -> None:
        """Archive status period to history."""
        values = {
            "equip_code": period.code,
            "equip_status": period.status.code,  # FIXED: Through Value Object
            "start_time": period.start_time,
            "end_time": period.end_time,
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

    async def save_many_to_history(self, periods: Sequence[DeviceHistory]) -> int:
        """Archive multiple status periods."""
        if not periods:
            return 0
        values = [
            {
                "equip_code": p.code,
                "equip_status": p.status.code,  # FIXED: Through Value Object
                "start_time": p.start_time,
                "end_time": p.end_time,
                "duration": p.duration_seconds,
            }
            for p in periods
        ]
        total = 0
        for i in range(0, len(values), self.BATCH_SIZE):
            batch = values[i : i + self.BATCH_SIZE]
            stmt = sqlite_insert(StatusHistory).values(batch)
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
            total += len(batch)
        return total

    async def get_by_status(self, status: Status, time_range: TimeRange | None = None) -> Sequence[DeviceHistory]:
        """
        Get status periods with specific status.

        Args:
            status: Status Value Object
            time_range: Optional time range filter

        Returns:
            Sequence of DeviceHistory entities
        """
        status_code = status.code

        if time_range:
            stmt = (
                select(StatusHistory)
                .where(StatusHistory.equip_status == status_code)
                .where(StatusHistory.start_time >= time_range.start)
                .where(StatusHistory.start_time <= time_range.end)
                .order_by(desc(StatusHistory.start_time))
            )
        else:
            stmt = select(StatusHistory).where(StatusHistory.equip_status == status_code).order_by(desc(StatusHistory.start_time))

        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return StatusPeriodOrmMapper.to_entities(rows)

    async def get_status_duration(self, code: EquipmentCode, status: Status, time_range: TimeRange) -> float:
        """
        Get total duration of a status.

        Args:
            code: Equipment code
            status: Status Value Object
            time_range: Time range to query

        Returns:
            Total duration in seconds
        """
        code_str = code.value
        status_code = status.code
        stmt = (
            select(func.sum(StatusHistory.duration))
            .where(StatusHistory.equip_code == code_str)
            .where(StatusHistory.equip_status == status_code)
            .where(StatusHistory.start_time >= time_range.start)
            .where(StatusHistory.start_time <= time_range.end)
        )
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            return result.scalar() or 0.0

    async def get_status_summary(self, code: EquipmentCode, time_range: TimeRange) -> Dict[str, float]:
        """
        Get duration summary for all statuses.

        Returns:
            Dictionary mapping technical status codes to total duration.
        """
        code_str = code.value
        stmt = (
            select(
                StatusHistory.equip_status,
                func.sum(StatusHistory.duration).label("total_duration"),
            )
            .where(StatusHistory.equip_code == code_str)
            .where(StatusHistory.start_time >= time_range.start)
            .where(StatusHistory.start_time <= time_range.end)
            .group_by(StatusHistory.equip_status)
        )
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            rows = result.all()

        summary = {}
        for row in rows:
            status_code = str(row[0])
            total_duration = float(row[1]) if row[1] else 0.0
            summary[status_code] = total_duration
        return summary

    async def delete_history_before(self, cutoff: datetime) -> int:
        """Delete history records before cutoff."""
        stmt = delete(StatusHistory).where(StatusHistory.start_time < cutoff)
        async with self._cold_engine.session() as session:
            result = await session.execute(stmt)
            return result.rowcount
