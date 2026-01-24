"""
SQLite implementation of DeviceRepository.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, delete, func
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from iFactory.domain import Device, DeviceRepository
from iFactory.domain.value_objects import EquipmentCode, Status
from iFactory.infrastructure.database import AsyncSQLiteEngine, LatestStatus
from ..mappers import DeviceOrmMapper

__all__ = ["SqliteDeviceRepository"]
logger = logging.getLogger(__name__)


class SqliteDeviceRepository(DeviceRepository):
    """
    SQLite implementation of DeviceRepository.

    Uses hot store (LatestStatus table) for device data.
    All status queries use raw technical codes; normalization is delegated upward.
    """

    __slots__ = ("_engine", "_initialized")

    def __init__(self, engine: AsyncSQLiteEngine):
        """
        Initialize repository.

        Args:
            engine: SQLite engine for hot store
        """
        self._engine = engine
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize repository (create tables)."""
        if self._initialized:
            return
        async with self._engine.engine.begin() as conn:
            await conn.run_sync(LatestStatus.metadata.create_all)
        self._initialized = True
        logger.debug("[DeviceRepository] Initialized")

    async def dispose(self) -> None:
        """Clean up resources."""
        pass

    async def get_by_code(self, code: str | EquipmentCode) -> Optional[Device]:
        """Get device by equipment code."""
        code_str = code.value if isinstance(code, EquipmentCode) else str(code)
        stmt = select(LatestStatus).where(LatestStatus.equip_code == code_str)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
            if row:
                return DeviceOrmMapper.to_entity(row)
            return None

    async def get_all(self) -> Sequence[Device]:
        """Get all devices."""
        stmt = select(LatestStatus).order_by(LatestStatus.equip_code)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return DeviceOrmMapper.to_entities(rows)

    async def get_by_codes(self, codes: Sequence[str] | Sequence[str]) -> Sequence[Device]:
        """Get devices by equipment codes."""
        if not codes:
            return []
        stmt = select(LatestStatus).where(LatestStatus.equip_code.in_(codes))
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return DeviceOrmMapper.to_entities(rows)

    async def get_by_status(self, status: Status) -> Sequence[Device]:
        """
        Get devices with specific status code or Status object.

        Args:
            status: Status Value Object

        Returns:
            Sequence of Device entities with that status
        """
        code_str = status.code
        stmt = select(LatestStatus).where(LatestStatus.equip_status == code_str)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return DeviceOrmMapper.to_entities(rows)

    async def get_by_status_codes(self, codes: Sequence[str]) -> Sequence[Device]:
        """
        Get devices with specific status codes.

        Args:
            codes: List of technical status codes (e.g., ["1", "3"])

        Returns:
            Sequence of Device entities with those status codes
        """
        if not codes:
            return []
        stmt = select(LatestStatus).where(LatestStatus.equip_status.in_(codes))
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return DeviceOrmMapper.to_entities(rows)

    async def exists(self, code: str | EquipmentCode) -> bool:
        """Check if device exists."""
        code_str = code.value if isinstance(code, EquipmentCode) else str(code)
        stmt = select(func.count()).select_from(LatestStatus).where(LatestStatus.equip_code == code_str)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return (result.scalar() or 0) > 0

    async def count(self) -> int:
        """Get total device count."""
        stmt = select(func.count()).select_from(LatestStatus)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return result.scalar() or 0

    async def save(self, device: Device) -> None:
        """Save device (insert or update)."""
        values = {
            "equip_code": device.code,
            "equip_status": device.status_code,
            "last_update": device.last_update or datetime.now(),
        }
        stmt = sqlite_insert(LatestStatus).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code"],
            set_={
                "equip_status": stmt.excluded.equip_status,
                "last_update": stmt.excluded.last_update,
            },
        )
        async with self._engine.session() as session:
            await session.execute(stmt)

    async def save_many(self, devices: Sequence[Device]) -> int:
        """Save multiple devices."""
        if not devices:
            return 0
        now = datetime.now()
        values = [
            {
                "equip_code": d.code,
                "equip_status": d.status_code,
                "last_update": d.last_update or now,
            }
            for d in devices
        ]
        stmt = sqlite_insert(LatestStatus).values(values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code"],
            set_={
                "equip_status": stmt.excluded.equip_status,
                "last_update": stmt.excluded.last_update,
            },
        )
        async with self._engine.session() as session:
            await session.execute(stmt)
        return len(devices)

    async def update_status(
        self,
        code: str | EquipmentCode,
        status_code: str | Status,
        update_time: Optional[datetime] = None,
    ) -> bool:
        """
        Update device status.

        Args:
            code: Equipment code
            status_code: Technical status code (e.g., "1") or Status Value Object.
            update_time: Optional timestamp
        """
        from iFactory.domain.value_objects import Status

        code_str = code.value if isinstance(code, EquipmentCode) else str(code)
        code_obj = status_code.code if isinstance(status_code, Status) else str(status_code)

        async with self._engine.session() as session:
            result = await session.execute(select(LatestStatus).where(LatestStatus.equip_code == code_str))
            row = result.scalar_one_or_none()
            if not row:
                return False
            row.equip_status = code_obj
            row.last_update = update_time or datetime.now()
            return True

    async def delete(self, code: str | EquipmentCode) -> bool:
        """Delete device."""
        code_str = code.value if isinstance(code, EquipmentCode) else str(code)
        stmt = delete(LatestStatus).where(LatestStatus.equip_code == code_str)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return (len(result.fetchall()) or 0) > 0

    async def delete_all(self) -> int:
        """Delete all devices."""
        stmt = delete(LatestStatus)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return len(result.fetchall())

    async def get_running_devices(self) -> Sequence[Device]:
        """
        Get devices currently running.

        Note: This method is deprecated as it hard-codes business logic.
        Use get_by_status_codes() with Domain enum codes instead.
        """

        running_codes = [s.code for s in DeviceStatus.running_statuses()]
        return await self.get_by_status_codes(running_codes)
