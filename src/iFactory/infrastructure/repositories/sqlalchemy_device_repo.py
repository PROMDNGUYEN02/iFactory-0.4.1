"""
Generic SQLAlchemy implementation of the Domain DeviceRepository.
Compatible with SQLite, Postgres, MSSQL.
"""

from __future__ import annotations
from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.infrastructure.persistence.sqlalchemy.models import DeviceORM
from iFactory.infrastructure.mappers.orm_mapper import OrmDeviceMapper


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    Persists and reconstructs Device aggregates using generic SQLAlchemy.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        stmt = select(DeviceORM).where(DeviceORM.equip_code == code.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model) if model else None

    async def get_all(self) -> Sequence[Device]:
        stmt = select(DeviceORM).order_by(DeviceORM.equip_code)
        result = await self._session.execute(stmt)
        return OrmDeviceMapper.to_entities(result.scalars().all())

    async def save(self, device: Device) -> None:
        """
        Database agnostic Upsert operation using session.merge.
        """
        orm_model = OrmDeviceMapper.to_model(device)
        await self._session.merge(orm_model)

    async def delete(self, code: EquipmentCode) -> bool:
        stmt = delete(DeviceORM).where(DeviceORM.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.rowcount > 0
