"""
Infrastructure: Hot Storage Repository.
Implements the Domain DeviceRepository interface for current state.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Sequence

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.infrastructure.persistence.sqlalchemy.models import DeviceModel, LatestMaterialInputModel
from iFactory.infrastructure.persistence.sqlalchemy.mapper import OrmDeviceMapper


class HotRepository(DeviceRepository):
    """
    Manages latest state of devices in the Hot Store.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Domain Interface Implementation ---

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

    # --- Extended Hot Store Methods (Non-Domain) ---

    async def get_by_id(self, id: str) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model)

    async def get_latest_material_input(self, equip_code: str) -> Optional[dict]:
        stmt = select(LatestMaterialInputModel).where(LatestMaterialInputModel.equipment_code == equip_code)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return {
            "equipment_code": model.equipment_code,
            "material_batch": model.material_batch,
            "feeding_time": model.feeding_time,
        }

    async def save_latest_material_input(
        self,
        equip_code: str,
        material_batch: str,
        feeding_time: datetime,
    ) -> None:
        from uuid import uuid4

        model = LatestMaterialInputModel(
            id=str(uuid4()),
            equipment_code=equip_code,
            material_batch=material_batch,
            feeding_time=feeding_time,
        )
        await self._session.merge(model)
