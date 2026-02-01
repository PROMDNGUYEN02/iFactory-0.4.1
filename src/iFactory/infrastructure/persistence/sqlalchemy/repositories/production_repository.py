"""
Production Repository - History storage only.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Sequence, List

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.repositories.production_repository import ProductionRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.persistence.sqlalchemy.models import (
    StatusHistoryModel,
    MaterialInputHistoryModel,
)
from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper


@dataclass
class HistoryRecord:
    """Simple data class for history records."""

    device_code: str
    status_code: int
    status_name: str
    start_time: datetime
    end_time: Optional[datetime]


class SqlAlchemyProductionRepository(ProductionRepository):
    """Repository for production history data."""

    STATUS_NAMES = {
        0: "Unknown",
        1: "Running",
        2: "Shutdown",
        3: "Stopped",
        4: "Maintenance",
        5: "Alarm",
    }

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_status(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        stmt = select(StatusHistoryModel).where(StatusHistoryModel.equip_code == code.value).order_by(desc(StatusHistoryModel.start_time)).limit(1)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SQLAlchemyMapper.to_status_period(model)

    async def get_status_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[StatusPeriod]:
        stmt = (
            select(StatusHistoryModel)
            .where(
                StatusHistoryModel.equip_code == code.value,
                StatusHistoryModel.start_time <= window.end,
                (StatusHistoryModel.end_time == None) | (StatusHistoryModel.end_time >= window.start),
            )
            .order_by(StatusHistoryModel.start_time)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_status_period(m) for m in models if m]

    async def get_history(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[HistoryRecord]:
        """Get history records for a device within a time range."""
        stmt = (
            select(StatusHistoryModel)
            .where(
                StatusHistoryModel.equip_code == equip_code,
                StatusHistoryModel.start_time <= end_time,
                (StatusHistoryModel.end_time == None) | (StatusHistoryModel.end_time >= start_time),
            )
            .order_by(StatusHistoryModel.start_time)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()

        records = []
        for model in models:
            status_code = model.equip_status
            status_name = self.STATUS_NAMES.get(status_code, "Unknown")

            records.append(
                HistoryRecord(
                    device_code=model.equip_code,
                    status_code=status_code,
                    status_name=status_name,
                    start_time=model.start_time,
                    end_time=model.end_time,
                )
            )

        return records

    async def save_status_period(
        self,
        period: StatusPeriod,
        equip_name: Optional[str] = None,
    ) -> None:
        model = SQLAlchemyMapper.to_status_period_model(period, equip_name=equip_name)
        await self._session.merge(model)

    async def bulk_save_status_history(
        self,
        periods: List[StatusPeriod],
        equip_name: Optional[str] = None,
    ) -> None:
        if not periods:
            return
        models = [SQLAlchemyMapper.to_status_period_model(p, equip_name=equip_name) for p in periods]
        self._session.add_all(models)

    async def get_latest_input(self, code: EquipmentCode) -> Optional[MaterialInput]:
        stmt = (
            select(MaterialInputHistoryModel)
            .where(MaterialInputHistoryModel.equipment_code == code.value)
            .order_by(desc(MaterialInputHistoryModel.feeding_time))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SQLAlchemyMapper.to_material_input(model)

    async def get_input_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[MaterialInput]:
        stmt = (
            select(MaterialInputHistoryModel)
            .where(
                MaterialInputHistoryModel.equipment_code == code.value,
                MaterialInputHistoryModel.feeding_time >= window.start,
                MaterialInputHistoryModel.feeding_time <= window.end,
            )
            .order_by(MaterialInputHistoryModel.feeding_time)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_material_input(m) for m in models if m]

    async def save_material_input(self, record: MaterialInput) -> None:
        model = SQLAlchemyMapper.to_material_history_model(record)
        self._session.add(model)


__all__ = ["SqlAlchemyProductionRepository", "HistoryRecord"]
