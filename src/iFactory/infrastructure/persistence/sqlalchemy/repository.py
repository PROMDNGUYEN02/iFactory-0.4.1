"""
Infrastructure: Async Repository Implementation.
Separated Hot and Cold Storage repositories.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Sequence

from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.entities.device import Device
from iFactory.domain.repositories.device_repository import DeviceRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.status_period import StatusPeriod

from .models import (
    DeviceModel,
    LatestMaterialInputModel,
    StatusPeriodModel,
    MaterialInputHistoryModel,
)
from .mapper import OrmDeviceMapper


# =============================================================================
# HOT STORAGE REPOSITORY - Latest State
# =============================================================================


class HotStorageRepository(DeviceRepository):
    """
    Repository for Hot Storage (latest state).
    - Latest device status
    - Latest material input
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # Device Operations (Latest Status)
    # -------------------------------------------------------------------------

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

    async def get_by_id(self, id: str) -> Optional[Device]:
        stmt = select(DeviceModel).where(DeviceModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return OrmDeviceMapper.to_entity(model)

    # -------------------------------------------------------------------------
    # Latest Material Input Operations
    # -------------------------------------------------------------------------

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


# =============================================================================
# COLD STORAGE REPOSITORY - History
# =============================================================================


class ColdStorageRepository:
    """
    Repository for Cold Storage (history).
    - Status periods history (for Gantt)
    - Material input history
    Supports: 24h, 7d, 30d, 60d retention.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # -------------------------------------------------------------------------
    # Status History Operations
    # -------------------------------------------------------------------------

    async def get_history(
        self,
        equip_code: str,
        start: datetime,
        end: datetime,
    ) -> List[StatusPeriod]:
        """Get status history within time range."""
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

    async def get_history_24h(self, equip_code: str) -> List[StatusPeriod]:
        """Get last 24 hours history."""
        end = datetime.now()
        start = end - timedelta(hours=24)
        return await self.get_history(equip_code, start, end)

    async def get_history_days(
        self,
        equip_code: str,
        days: int,
    ) -> List[StatusPeriod]:
        """Get history for specified days (7, 30, 60, etc.)."""
        end = datetime.now()
        start = end - timedelta(days=days)
        return await self.get_history(equip_code, start, end)

    async def get_active_period(self, equip_code: str) -> Optional[StatusPeriod]:
        """Get the currently active (unclosed) period."""
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
        """Add a new status period."""
        model = OrmDeviceMapper.to_period_model(period)
        self._session.add(model)

    async def update_period(self, period: StatusPeriod) -> None:
        """Update an existing period (e.g., close it)."""
        model = OrmDeviceMapper.to_period_model(period)
        await self._session.merge(model)

    async def cleanup_old_history(self, retention_days: int) -> int:
        """
        Delete history older than retention period.
        Returns number of deleted records.
        """
        cutoff = datetime.now() - timedelta(days=retention_days)
        stmt = delete(StatusPeriodModel).where(StatusPeriodModel.start_time < cutoff)
        result = await self._session.execute(stmt)
        return result.rowcount

    # -------------------------------------------------------------------------
    # Material Input History Operations
    # -------------------------------------------------------------------------

    async def get_material_history(
        self,
        equip_code: str,
        start: datetime,
        end: datetime,
    ) -> List[dict]:
        """Get material input history within time range."""
        stmt = (
            select(MaterialInputHistoryModel)
            .where(
                MaterialInputHistoryModel.equipment_code == equip_code,
                MaterialInputHistoryModel.feeding_time >= start,
                MaterialInputHistoryModel.feeding_time <= end,
            )
            .order_by(MaterialInputHistoryModel.feeding_time)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [
            {
                "equipment_code": m.equipment_code,
                "material_batch": m.material_batch,
                "feeding_time": m.feeding_time,
                "recorded_at": m.recorded_at,
            }
            for m in models
        ]

    async def add_material_history(
        self,
        equip_code: str,
        material_batch: str,
        feeding_time: datetime,
    ) -> None:
        """Add material input to history."""
        from uuid import uuid4

        model = MaterialInputHistoryModel(
            id=str(uuid4()),
            equipment_code=equip_code,
            material_batch=material_batch,
            feeding_time=feeding_time,
            recorded_at=datetime.now(),
        )
        self._session.add(model)

    async def cleanup_old_material_history(self, retention_days: int) -> int:
        """Delete material history older than retention period."""
        cutoff = datetime.now() - timedelta(days=retention_days)
        stmt = delete(MaterialInputHistoryModel).where(MaterialInputHistoryModel.recorded_at < cutoff)
        result = await self._session.execute(stmt)
        return result.rowcount


# Backward compatibility alias
SqlAlchemyDeviceRepository = HotStorageRepository


__all__ = [
    "HotStorageRepository",
    "ColdStorageRepository",
    "SqlAlchemyDeviceRepository",
]
