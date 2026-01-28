"""
Infrastructure: Cold Storage Repository.
Manages historical data (logs, timelines).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.infrastructure.persistence.sqlalchemy.models import StatusPeriodModel, MaterialInputHistoryModel
from iFactory.infrastructure.persistence.sqlalchemy.mapper import OrmDeviceMapper


class ColdRepository:
    """
    Manages historical records in Cold Store.
    NOT a Domain Repository, but a specialized History Service Adapter.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # --- Status History ---

    async def get_history(self, equip_code: str, start: datetime, end: datetime) -> List[StatusPeriod]:
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
        end = datetime.now()
        start = end - timedelta(hours=24)
        return await self.get_history(equip_code, start, end)

    async def get_history_days(self, equip_code: str, days: int) -> List[StatusPeriod]:
        end = datetime.now()
        start = end - timedelta(days=days)
        return await self.get_history(equip_code, start, end)

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

    async def cleanup_old_history(self, retention_days: int) -> int:
        cutoff = datetime.now() - timedelta(days=retention_days)
        stmt = delete(StatusPeriodModel).where(StatusPeriodModel.start_time < cutoff)
        result = await self._session.execute(stmt)
        return result.rowcount

    # --- Material History ---

    async def get_material_history(self, equip_code: str, start: datetime, end: datetime) -> List[dict]:
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

    async def add_material_history(self, equip_code: str, material_batch: str, feeding_time: datetime) -> None:
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
        cutoff = datetime.now() - timedelta(days=retention_days)
        stmt = delete(MaterialInputHistoryModel).where(MaterialInputHistoryModel.recorded_at < cutoff)
        result = await self._session.execute(stmt)
        return result.rowcount
