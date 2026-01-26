"""
Concrete SQLAlchemy implementation of the Domain DeviceRepository.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.infrastructure.persistence.models import DeviceORM
from iFactory.infrastructure.mappers.device_mapper import DeviceMapper


class SqliteDeviceRepository(DeviceRepository):
    """
    Persists and reconstructs Device aggregates using SQLite/SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        stmt = select(DeviceORM).where(DeviceORM.equip_code == code.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return DeviceMapper.to_entity(model) if model else None

    async def get_all(self) -> Sequence[Device]:
        stmt = select(DeviceORM).order_by(DeviceORM.equip_code)
        result = await self._session.execute(stmt)
        return DeviceMapper.to_entities(result.scalars().all())

    async def save(self, device: Device) -> None:
        """
        Upsert operation. Ensures idempotency.
        """
        orm_model = DeviceMapper.to_model(device)

        values = {
            "id": orm_model.id,
            "equip_code": orm_model.equip_code,
            "equip_status": orm_model.equip_status,
            "last_update": orm_model.last_update,
            "is_active": orm_model.is_active,
        }

        stmt = sqlite_insert(DeviceORM).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code"], set_={"equip_status": stmt.excluded.equip_status, "last_update": stmt.excluded.last_update}
        )
        await self._session.execute(stmt)

    async def delete(self, code: EquipmentCode) -> bool:
        stmt = delete(DeviceORM).where(DeviceORM.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
