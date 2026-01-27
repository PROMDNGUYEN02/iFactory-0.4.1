"""
Infrastructure: Async Repository Implementation.
SQLAlchemy implementation of the Domain DeviceRepository.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Sequence

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod

from .models import DeviceModel, StatusPeriodModel
from .mapper import OrmDeviceMapper


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    Concrete implementation of DeviceRepository using SQLAlchemy Async.
    Implements all abstract methods from the Domain interface.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # =========================================================================
    # Required Abstract Methods from DeviceRepository
    # =========================================================================

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        return await self.get_by_code_string(code.value)

    async def get_by_code_string(self, code: str) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.equip_code == code.upper())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model)

    async def get_all(self) -> Sequence[Device]:
        stmt = select(DeviceModel).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return OrmDeviceMapper.to_entities(list(models))

    async def get_active(self) -> Sequence[Device]:
        stmt = select(DeviceModel).where(DeviceModel.is_active == True).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return OrmDeviceMapper.to_entities(list(models))

    async def save(self, device: Device) -> None:
        orm_model = OrmDeviceMapper.to_model(device)
        await self._session.merge(orm_model)

    async def save_many(self, devices: Sequence[Device]) -> None:
        for device in devices:
            orm_model = OrmDeviceMapper.to_model(device)
            await self._session.merge(orm_model)

    async def delete(self, code: EquipmentCode) -> bool:
        stmt = delete(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists(self, code: EquipmentCode) -> bool:
        stmt = select(func.count()).select_from(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return count > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(DeviceModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # =========================================================================
    # Extended Methods (History Support)
    # =========================================================================

    async def get_by_id(self, id: str) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model)

    async def get_history(
        self,
        equip_code: str,
        start: datetime,
        end: datetime,
    ) -> List[StatusPeriod]:
        stmt = (
            select(StatusPeriodModel)
            .where(
                StatusPeriodModel.device_id == equip_code,
                StatusPeriodModel.start_time >= start,
                StatusPeriodModel.start_time <= end,
            )
            .order_by(StatusPeriodModel.start_time)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return OrmDeviceMapper.to_period_entities(list(models))

    async def get_active_period(self, equip_code: str) -> Optional[StatusPeriod]:
        stmt = (
            select(StatusPeriodModel)
            .where(
                StatusPeriodModel.device_id == equip_code,
                StatusPeriodModel.end_time.is_(None),
            )
            .order_by(StatusPeriodModel.start_time.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_period_entity(model)

    async def add_period(self, period: StatusPeriod) -> None:
        model = OrmDeviceMapper.to_period_model(period)
        self._session.add(model)

    async def update_period(self, period: StatusPeriod) -> None:
        model = OrmDeviceMapper.to_period_model(period)
        await self._session.merge(model)
