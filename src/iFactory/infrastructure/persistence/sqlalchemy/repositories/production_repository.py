from __future__ import annotations

from typing import Optional, Sequence
from datetime import datetime
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.repositories.production_repository import ProductionRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.persistence.sqlalchemy.models import StatusHistoryModel, MaterialInputHistoryModel

# FIXED: Import from .mapper (singular) instead of .mappers
from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper


class SqlAlchemyProductionRepository(ProductionRepository):
    """
    Cold Store Implementation of ProductionRepository.
    Manages historical timelines and material inputs.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_latest_status(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        """
        Fetches the active status period (end_time is None) or the most recent one.
        """
        stmt = select(StatusHistoryModel).where(StatusHistoryModel.equip_code == code.value).order_by(desc(StatusHistoryModel.start_time)).limit(1)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SQLAlchemyMapper.to_status_period(model)

    async def get_status_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]:
        """
        Fetches status history overlapping with the given window.
        """
        stmt = (
            select(StatusHistoryModel)
            .where(
                StatusHistoryModel.equip_code == code.value,
                # Start time must be before window end
                StatusHistoryModel.start_time <= window.end,
                # End time must be after window start, OR End time is NULL (active) AND Start time is before window end
                (StatusHistoryModel.end_time == None) | (StatusHistoryModel.end_time >= window.start),
            )
            .order_by(StatusHistoryModel.start_time)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [SQLAlchemyMapper.to_status_period(m) for m in models if m]

    async def save_status_period(self, period: StatusPeriod) -> None:
        model = SQLAlchemyMapper.to_status_period_model(period)
        await self._session.merge(model)

    async def get_latest_input(self, code: EquipmentCode) -> Optional[MaterialInput]:
        """
        Fetches the most recent material input from history.
        """
        stmt = (
            select(MaterialInputHistoryModel)
            .where(MaterialInputHistoryModel.equipment_code == code.value)
            .order_by(desc(MaterialInputHistoryModel.feeding_time))
            .limit(1)
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SQLAlchemyMapper.to_material_input(model)

    async def get_input_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]:
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
