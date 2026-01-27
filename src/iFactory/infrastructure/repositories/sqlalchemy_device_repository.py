from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.infrastructure.persistence.sqlalchemy.models import DeviceModel
from iFactory.infrastructure.persistence.sqlalchemy.mappers import SqlAlchemyMapper


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    SQLAlchemy implementation of DeviceRepository.
    Interacts with Hot Storage (DeviceModel).
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SqlAlchemyMapper.to_device_entity(model)

    async def get_by_code_string(self, code: str) -> Optional[Device]:
        # Convenience method, delegate to typed method
        return await self.get_by_code(EquipmentCode(code))

    async def get_all(self) -> Sequence[Device]:
        stmt = select(DeviceModel).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [d for d in (SqlAlchemyMapper.to_device_entity(m) for m in models) if d is not None]

    async def get_active(self) -> Sequence[Device]:
        stmt = select(DeviceModel).where(DeviceModel.is_active.is_(True)).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [d for d in (SqlAlchemyMapper.to_device_entity(m) for m in models) if d is not None]

    async def save(self, device: Device) -> None:
        model = SqlAlchemyMapper.to_device_model(device)
        await self._session.merge(model)

    async def save_many(self, devices: Sequence[Device]) -> None:
        for device in devices:
            await self.save(device)

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
