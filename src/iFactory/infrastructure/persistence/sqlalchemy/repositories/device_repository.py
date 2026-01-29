from __future__ import annotations

from typing import Optional, Sequence, Tuple
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.infrastructure.persistence.sqlalchemy.models import DeviceModel, LatestMaterialInputModel

from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper


class SqlAlchemyDeviceRepository(DeviceRepository):
    """
    Hot Store Implementation of DeviceRepository.
    Manages current state of devices.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.equip_code == code.value.upper())
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SQLAlchemyMapper.to_device_entity(model)

    async def get_all(self) -> Sequence[Device]:
        stmt = select(DeviceModel).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_device_entity(m) for m in models if m]

    async def get_dashboard_snapshot(self) -> Sequence[Tuple[Device, Optional[MaterialInput]]]:
        """
        Optimized join query to fetch Device + Latest Material Input in one go.
        """
        stmt = (
            select(DeviceModel, LatestMaterialInputModel)
            .outerjoin(LatestMaterialInputModel, DeviceModel.equip_code == LatestMaterialInputModel.equipment_code)
            .order_by(DeviceModel.equip_code)
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        snapshot = []
        for dev_model, input_model in rows:
            if not dev_model:
                continue

            device_entity = SQLAlchemyMapper.to_device_entity(dev_model)
            material_vo = None
            if input_model:
                try:
                    material_vo = SQLAlchemyMapper.to_material_input(input_model)
                except Exception:
                    from iFactory.domain.value_objects.material_input import MaterialInput
                    from iFactory.domain.value_objects.material_batch import MaterialBatch

                    material_vo = MaterialInput(
                        equipment_code=EquipmentCode(input_model.equipment_code),
                        material_batch=MaterialBatch(input_model.material_batch),
                        feeding_time=input_model.feeding_time,
                    )

            if device_entity:
                snapshot.append((device_entity, material_vo))

        return snapshot

    async def get_active(self) -> Sequence[Device]:
        stmt = select(DeviceModel).where(DeviceModel.is_active == True).order_by(DeviceModel.equip_code)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_device_entity(m) for m in models if m]

    async def save(self, device: Device) -> None:
        model = SQLAlchemyMapper.to_device_model(device)
        await self._session.merge(model)

    async def delete(self, code: EquipmentCode) -> bool:
        stmt = delete(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.rowcount > 0

    async def exists(self, code: EquipmentCode) -> bool:
        stmt = select(func.count()).select_from(DeviceModel).where(DeviceModel.equip_code == code.value)
        result = await self._session.execute(stmt)
        return result.scalar_one() > 0

    async def count(self) -> int:
        stmt = select(func.count()).select_from(DeviceModel)
        result = await self._session.execute(stmt)
        return result.scalar_one()
