"""
Infrastructure: Async Repository Implementation.
Generic SQLAlchemy implementation of the Domain DeviceRepository.
"""

from __future__ import annotations
from typing import List, Optional
from datetime import datetime
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

# Import Domain Entities & Repository Interface
from iFactory.domain.entities.device import Device
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.repositories.device_repository import DeviceRepository

# Import Infrastructure Models & Mapper
from iFactory.infrastructure.persistence.sqlalchemy.models import DeviceModel, StatusPeriodModel
from iFactory.infrastructure.persistence.sqlalchemy.mapper import OrmDeviceMapper


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    Implementation cụ thể của DeviceRepository sử dụng SQLAlchemy Async.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_all(self) -> List[Device]:
        stmt = select(DeviceModel).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return OrmDeviceMapper.to_entities(models)

    async def get_by_code(self, code: str) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.equip_code == code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model) if model else None

    # Alias for compatibility
    get_by_equipment_code = get_by_code

    async def get_by_id(self, id: str) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model) if model else None

    async def save(self, device: Device) -> None:
        orm_model = OrmDeviceMapper.to_model(device)
        await self._session.merge(orm_model)

    async def save_many(self, devices: List[Device]) -> int:
        count = 0
        for device in devices:
            orm_model = OrmDeviceMapper.to_model(device)
            await self._session.merge(orm_model)
            count += 1
        return count

    async def delete(self, device: Device) -> None:
        stmt = delete(DeviceModel).where(DeviceModel.equip_code == device.equipment_code.value)
        await self._session.execute(stmt)

    # --- History Implementation ---

    async def get_history(self, equip_code: str, start: datetime, end: datetime) -> List[StatusPeriod]:
        stmt = (
            select(StatusPeriodModel)
            .where(
                StatusPeriodModel.device_id == equip_code,
                StatusPeriodModel.start_time >= start,
                # Có thể thêm điều kiện <= end tùy logic hiển thị
            )
            .order_by(StatusPeriodModel.start_time)
        )
        result = await self._session.execute(stmt)
        return [OrmDeviceMapper.to_period_entity(m) for m in result.scalars().all()]

    async def get_active_period(self, equip_code: str) -> Optional[StatusPeriod]:
        stmt = (
            select(StatusPeriodModel)
            .where(StatusPeriodModel.device_id == equip_code, StatusPeriodModel.end_time.is_(None))
            .order_by(StatusPeriodModel.start_time.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        return OrmDeviceMapper.to_period_entity(result.scalar_one_or_none())

    async def add_period(self, period: StatusPeriod) -> None:
        model = OrmDeviceMapper.to_period_model(period)
        self._session.add(model)

    async def update_period(self, period: StatusPeriod) -> None:
        # Sử dụng merge để update record đã tồn tại
        model = OrmDeviceMapper.to_period_model(period)
        await self._session.merge(model)
