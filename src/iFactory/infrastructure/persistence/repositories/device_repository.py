from __future__ import annotations
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.infrastructure.database.models import DeviceORM
from iFactory.infrastructure.mappers.device_mapper import DeviceMapper


class SqliteDeviceRepository(DeviceRepository):
    """
    SQLAlchemy implementation of the DeviceRepository.
    Relies entirely on the injected AsyncSession from the Unit of Work.
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
        values = {
            "id": device.code,
            "equip_code": device.code,
            "equip_status": device.current_status.value,
            "last_update": device.last_update or datetime.now(),
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
