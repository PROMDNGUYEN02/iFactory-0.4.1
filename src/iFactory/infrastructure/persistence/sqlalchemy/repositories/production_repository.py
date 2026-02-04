# src/iFactory/infrastructure/persistence/sqlalchemy/repositories/production_repository.py
"""
Production Repository - History storage implementation.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import select, desc, update, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.repositories.production_repository import (
    ProductionRepository,
    HistoryRecord,
)
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.persistence.sqlalchemy.models import (
    StatusHistoryModel,
    MaterialInputHistoryModel,
)
from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper

logger = logging.getLogger(__name__)


class SqlAlchemyProductionRepository(ProductionRepository):
    """Repository for production history data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ========================================================================
    # Status History
    # ========================================================================

    async def get_latest_status(
        self,
        code: EquipmentCode,
    ) -> Optional[StatusPeriod]:
        """Get the most recent status period for a device."""
        try:
            stmt = (
                select(StatusHistoryModel).where(StatusHistoryModel.equip_code == code.value).order_by(desc(StatusHistoryModel.start_time)).limit(1)
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            return SQLAlchemyMapper.to_status_period(model)
        except Exception as e:
            logger.error(f"Error getting latest status for {code.value}: {e}")
            return None

    async def get_status_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[StatusPeriod]:
        """Get all status periods overlapping the time window."""
        try:
            end_time = window.end or datetime.now()

            stmt = (
                select(StatusHistoryModel)
                .where(
                    StatusHistoryModel.equip_code == code.value,
                    StatusHistoryModel.start_time <= end_time,
                    ((StatusHistoryModel.end_time.is_(None)) | (StatusHistoryModel.end_time >= window.start)),
                )
                .order_by(StatusHistoryModel.start_time)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            return [p for p in (SQLAlchemyMapper.to_status_period(m) for m in models) if p is not None]
        except Exception as e:
            logger.error(f"Error getting status history for {code.value}: {e}")
            return []

    async def get_history(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[HistoryRecord]:
        """Get history records for a device within a time range."""
        try:
            stmt = (
                select(StatusHistoryModel)
                .where(
                    StatusHistoryModel.equip_code == equip_code.upper(),
                    StatusHistoryModel.start_time <= end_time,
                    ((StatusHistoryModel.end_time.is_(None)) | (StatusHistoryModel.end_time >= start_time)),
                )
                .order_by(StatusHistoryModel.start_time)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            records: List[HistoryRecord] = []
            for model in models:
                records.append(
                    HistoryRecord(
                        equipment_code=model.equip_code,
                        status=model.equip_status,
                        start_time=model.start_time,
                        end_time=model.end_time,
                        equip_name=model.equip_name,
                        reason_code=model.reason_code,
                    )
                )

            return records
        except Exception as e:
            logger.error(f"Error getting history for {equip_code}: {e}")
            return []

    async def get_history_bulk(
        self,
        equip_codes: List[str],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Sequence[HistoryRecord]]:
        """Get history records for multiple devices."""
        if not equip_codes:
            return {}

        try:
            upper_codes = [c.upper() for c in equip_codes]

            stmt = (
                select(StatusHistoryModel)
                .where(
                    StatusHistoryModel.equip_code.in_(upper_codes),
                    StatusHistoryModel.start_time <= end_time,
                    ((StatusHistoryModel.end_time.is_(None)) | (StatusHistoryModel.end_time >= start_time)),
                )
                .order_by(
                    StatusHistoryModel.equip_code,
                    StatusHistoryModel.start_time,
                )
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            # Group by equipment code
            grouped: Dict[str, List[HistoryRecord]] = {code: [] for code in upper_codes}

            for model in models:
                record = HistoryRecord(
                    equipment_code=model.equip_code,
                    status=model.equip_status,
                    start_time=model.start_time,
                    end_time=model.end_time,
                    equip_name=model.equip_name,
                    reason_code=model.reason_code,
                )
                grouped[model.equip_code].append(record)

            return grouped
        except Exception as e:
            logger.error(f"Error getting bulk history: {e}")
            return {code.upper(): [] for code in equip_codes}

    async def save_status_period(
        self,
        period: StatusPeriod,
        equip_name: Optional[str] = None,
    ) -> None:
        """Record a single status period."""
        try:
            model = SQLAlchemyMapper.to_status_period_model(
                period,
                equip_name=equip_name,
            )
            await self._session.merge(model)
        except Exception as e:
            logger.error(f"Error saving status period: {e}")
            raise

    async def bulk_save_status_history(
        self,
        periods: List[StatusPeriod],
        equip_name: Optional[str] = None,
    ) -> None:
        """Bulk save multiple status periods."""
        if not periods:
            return

        try:
            models = [SQLAlchemyMapper.to_status_period_model(p, equip_name=equip_name) for p in periods]
            self._session.add_all(models)
            logger.debug(f"Bulk saved {len(periods)} status periods")
        except Exception as e:
            logger.error(f"Error bulk saving status history: {e}")
            raise

    async def close_open_period(
        self,
        code: EquipmentCode,
        end_time: datetime,
    ) -> bool:
        """Close any open (ongoing) period for a device."""
        try:
            stmt = (
                update(StatusHistoryModel)
                .where(
                    StatusHistoryModel.equip_code == code.value,
                    StatusHistoryModel.end_time.is_(None),
                )
                .values(end_time=end_time)
            )
            result = await self._session.execute(stmt)
            return result.rowcount > 0
        except Exception as e:
            logger.error(f"Error closing open period for {code.value}: {e}")
            return False

    # ========================================================================
    # Material Input
    # ========================================================================

    async def get_latest_input(
        self,
        code: EquipmentCode,
    ) -> Optional[MaterialInput]:
        """Get the most recent material input for a device."""
        try:
            stmt = (
                select(MaterialInputHistoryModel)
                .where(MaterialInputHistoryModel.equipment_code == code.value)
                .order_by(desc(MaterialInputHistoryModel.feeding_time))
                .limit(1)
            )
            result = await self._session.execute(stmt)
            model = result.scalar_one_or_none()
            return SQLAlchemyMapper.to_material_input(model)
        except Exception as e:
            logger.error(f"Error getting latest input for {code.value}: {e}")
            return None

    async def get_input_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[MaterialInput]:
        """Get material inputs during the time window."""
        try:
            end_time = window.end or datetime.now()

            stmt = (
                select(MaterialInputHistoryModel)
                .where(
                    MaterialInputHistoryModel.equipment_code == code.value,
                    MaterialInputHistoryModel.feeding_time >= window.start,
                    MaterialInputHistoryModel.feeding_time <= end_time,
                )
                .order_by(MaterialInputHistoryModel.feeding_time)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            return [m for m in (SQLAlchemyMapper.to_material_input(model) for model in models) if m is not None]
        except Exception as e:
            logger.error(f"Error getting input history for {code.value}: {e}")
            return []

    async def save_material_input(self, record: MaterialInput) -> None:
        """Persist a material input record."""
        try:
            model = SQLAlchemyMapper.to_material_history_model(record)
            self._session.add(model)
        except Exception as e:
            logger.error(f"Error saving material input: {e}")
            raise

    # ========================================================================
    # Statistics
    # ========================================================================

    async def get_status_summary(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Dict[MachineStatus, float]:
        """Get summary of time spent in each status."""
        try:
            periods = await self.get_status_history(code, window)

            summary: Dict[MachineStatus, float] = {}
            now = datetime.now()

            for period in periods:
                # Clamp to window
                start = max(period.start, window.start)
                end = min(
                    period.end or now,
                    window.end or now,
                )

                if end > start:
                    duration = (end - start).total_seconds()
                    if period.status in summary:
                        summary[period.status] += duration
                    else:
                        summary[period.status] = duration

            return summary
        except Exception as e:
            logger.error(f"Error getting status summary for {code.value}: {e}")
            return {}

    async def get_oee_metrics(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Dict[str, float]:
        """Calculate OEE metrics."""
        try:
            summary = await self.get_status_summary(code, window)

            total_time = window.duration_seconds
            if total_time <= 0:
                return {
                    "availability": 0.0,
                    "performance": 0.0,
                    "quality": 1.0,
                    "oee": 0.0,
                }

            run_time = summary.get(MachineStatus.RUNNING, 0.0)

            # Availability = Run Time / Total Time
            availability = run_time / total_time if total_time > 0 else 0.0

            # For now, assume performance and quality are 100%
            # These would need production data to calculate properly
            performance = 1.0
            quality = 1.0

            oee = availability * performance * quality

            return {
                "availability": round(availability, 4),
                "performance": round(performance, 4),
                "quality": round(quality, 4),
                "oee": round(oee, 4),
                "run_time_seconds": run_time,
                "total_time_seconds": total_time,
            }
        except Exception as e:
            logger.error(f"Error calculating OEE for {code.value}: {e}")
            return {
                "availability": 0.0,
                "performance": 0.0,
                "quality": 0.0,
                "oee": 0.0,
            }


__all__ = ["SqlAlchemyProductionRepository"]
