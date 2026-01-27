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
from iFactory.domain.enums.machine_status import MachineStatus
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

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """Get device by EquipmentCode value object."""
        return await self.get_by_code_string(code.value)

    async def get_by_code_string(self, code: str) -> Optional[Device]:
        """Get device by raw equipment code string."""
        stmt = select(DeviceModel).where(DeviceModel.equip_code == code.upper())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model) if model else None

    async def get_all(self) -> Sequence[Device]:
        """Get all devices ordered by equipment code."""
        stmt = select(DeviceModel).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return OrmDeviceMapper.to_entities(list(models))

    async def get_active(self) -> Sequence[Device]:
        """Get all devices that are currently active (not shutdown/unknown)."""
        stmt = select(DeviceModel).where(DeviceModel.is_active == True).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return OrmDeviceMapper.to_entities(list(models))

    async def save(self, device: Device) -> None:
        """Save or update a device."""
        orm_model = OrmDeviceMapper.to_model(device)
        await self._session.merge(orm_model)

    async def save_many(self, devices: Sequence[Device]) -> None:
        """Save or update multiple devices."""
        for device in devices:
            orm_model = OrmDeviceMapper.to_model(device)
            await self._session.merge(orm_model)

    async def delete(self, code: EquipmentCode) -> bool:
        """Delete a device by equipment code. Returns True if deleted."""
        stmt = delete(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists(self, code: EquipmentCode) -> bool:
        """Check if a device exists by equipment code."""
        stmt = select(func.count()).select_from(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        count = result.scalar_one()
        return count > 0

    async def count(self) -> int:
        """Count total number of devices."""
        stmt = select(func.count()).select_from(DeviceModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # --- Extended Methods for History (not in base interface) ---

    async def get_by_id(self, id: str) -> Optional[Device]:
        """Get device by primary key ID."""
        stmt = select(DeviceModel).where(DeviceModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model) if model else None

    async def get_history(
        self,
        equip_code: str,
        start: datetime,
        end: datetime,
    ) -> List[StatusPeriod]:
        """Get status history for a device within a time range."""
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
        return [OrmDeviceMapper.to_period_entity(m) for m in models if m is not None]

    async def get_active_period(self, equip_code: str) -> Optional[StatusPeriod]:
        """Get the currently active (open-ended) status period."""
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
        return OrmDeviceMapper.to_period_entity(model) if model else None

    async def add_period(self, period: StatusPeriod) -> None:
        """Add a new status period."""
        model = OrmDeviceMapper.to_period_model(period)
        self._session.add(model)

    async def update_period(self, period: StatusPeriod) -> None:
        """Update an existing status period."""
        model = OrmDeviceMapper.to_period_model(period)
        await self._session.merge(model)
