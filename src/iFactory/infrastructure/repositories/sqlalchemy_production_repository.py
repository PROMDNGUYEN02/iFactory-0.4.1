from __future__ import annotations

from typing import Optional, Sequence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.repositories.production_repository import ProductionRepository
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.persistence.sqlalchemy.models import (
    StatusPeriodModel,
    LatestMaterialInputModel,
    MaterialInputHistoryModel,
)
from iFactory.infrastructure.persistence.sqlalchemy.mappers import SqlAlchemyMapper


class SqlAlchemyProductionRepository(ProductionRepository):
    """
    SQLAlchemy implementation of ProductionRepository.
    Interacts with Cold Storage (StatusPeriodModel, MaterialInputHistoryModel)
    and Hot Storage for latest material (LatestMaterialInputModel).
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    # =========================================================================
    # Status Periods
    # =========================================================================

    async def get_latest_status(
        self,
        code: EquipmentCode,
    ) -> Optional[StatusPeriod]:
        """
        Retrieves the most recent status period (ongoing or closed).
        """
        stmt = select(StatusPeriodModel).where(StatusPeriodModel.device_id == code.value).order_by(StatusPeriodModel.start_time.desc()).limit(1)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SqlAlchemyMapper.to_status_period(model)

    async def get_status_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[StatusPeriod]:
        """
        Retrieves status periods overlapping with the given window.
        """
        stmt = (
            select(StatusPeriodModel)
            .where(
                StatusPeriodModel.device_id == code.value,
                StatusPeriodModel.start_time >= window.start,
            )
            .order_by(StatusPeriodModel.start_time)
        )

        if window.end:
            stmt = stmt.where(StatusPeriodModel.start_time <= window.end)

        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return SqlAlchemyMapper.to_status_periods(models)

    async def save_status_period(self, period: StatusPeriod) -> None:
        # Note: Since StatusPeriod is immutable in domain but we need to create/update rows,
        # we treat 'save' as 'insert new' or 'update if we can resolve identity'.
        # Since domain VO doesn't have identity, this repo must handle the logic
        # of finding the 'latest open' to close it, or inserting a new one.
        # However, strictly following the interface:
        model = SqlAlchemyMapper.to_status_period_model(period)

        # If the domain provided a 'closed' period that matches an existing open record
        # in DB, a smarter merge strategy would be needed here.
        # For simplicity in this refactor, we assume basic append/merge behavior.
        await self._session.merge(model)

    async def save_status_periods(
        self,
        periods: Sequence[StatusPeriod],
    ) -> None:
        for period in periods:
            await self.save_status_period(period)

    async def count_status_periods(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(StatusPeriodModel)
            .where(StatusPeriodModel.device_id == code.value, StatusPeriodModel.start_time >= window.start)
        )
        if window.end:
            stmt = stmt.where(StatusPeriodModel.start_time <= window.end)

        result = await self._session.execute(stmt)
        return result.scalar_one()

    # =========================================================================
    # Material Inputs
    # =========================================================================

    async def get_latest_input(
        self,
        code: EquipmentCode,
    ) -> Optional[MaterialInput]:
        stmt = select(LatestMaterialInputModel).where(LatestMaterialInputModel.equipment_code == code.value)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return SqlAlchemyMapper.to_material_input(model)

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
            )
            .order_by(MaterialInputHistoryModel.feeding_time)
        )
        if window.end:
            stmt = stmt.where(MaterialInputHistoryModel.feeding_time <= window.end)

        result = await self._session.execute(stmt)
        models = result.scalars().all()

        inputs = []
        for m in models:
            inp = SqlAlchemyMapper.to_material_input(m)
            if inp:
                inputs.append(inp)
        return inputs

    async def save_material_input(self, record: MaterialInput) -> None:
        # 1. Save to History
        history_model = SqlAlchemyMapper.to_material_history_model(record)
        self._session.add(history_model)

        # 2. Update Latest
        latest_model = SqlAlchemyMapper.to_latest_material_model(record)
        await self._session.merge(latest_model)
