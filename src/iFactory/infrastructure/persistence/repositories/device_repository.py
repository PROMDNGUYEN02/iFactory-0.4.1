from __future__ import annotations
from datetime import datetime
from typing import Optional, Sequence
from sqlalchemy import select, delete
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.infrastructure.database.engines.sqlite_engine import AsyncSQLiteEngine
from iFactory.infrastructure.database.models.hot_models import DeviceStateModel
from iFactory.infrastructure.persistence.mappers.entity_mapper import EntityMapper


class SqliteDeviceRepository(DeviceRepository):
    def __init__(self, engine: AsyncSQLiteEngine):
        self._engine = engine

    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        stmt = select(DeviceStateModel).where(DeviceStateModel.equip_code == code.value)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            return EntityMapper.to_device_entity(model) if model else None

    async def get_all(self) -> Sequence[Device]:
        stmt = select(DeviceStateModel).order_by(DeviceStateModel.equip_code)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return [EntityMapper.to_device_entity(m) for m in result.scalars().all()]

    async def save(self, device: Device) -> None:
        values = {"equip_code": device.code, "equip_status": device.current_status.code, "last_update": device.last_update or datetime.now()}
        stmt = sqlite_insert(DeviceStateModel).values(**values)
        stmt = stmt.on_conflict_do_update(
            index_elements=["equip_code"], set_={"equip_status": stmt.excluded.equip_status, "last_update": stmt.excluded.last_update}
        )
        async with self._engine.session() as session:
            await session.execute(stmt)

    async def delete(self, code: EquipmentCode) -> bool:
        stmt = delete(DeviceStateModel).where(DeviceStateModel.equip_code == code.value)
        async with self._engine.session() as session:
            result = await session.execute(stmt)
            return result.rowcount > 0
