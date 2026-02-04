# src/iFactory/infrastructure/persistence/sqlalchemy/repositories/production_repository.py
"""
Production Repository - History storage implementation.

Implements the ProductionRepository port for SQLAlchemy/SQLite storage.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from sqlalchemy import select, desc, update, delete, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from iFactory.domain.enums.machine_status import MachineStatus
from iFactory.domain.repositories.production_repository import (
    ProductionRepository,
    HistoryRecord,
    OEEMetrics,
)
from iFactory.domain.value_objects.equipment_code import EquipmentCode
from iFactory.domain.value_objects.material_input import MaterialInput
from iFactory.domain.value_objects.material_batch import MaterialBatch
from iFactory.domain.value_objects.status_period import StatusPeriod
from iFactory.domain.value_objects.time_range import TimeRange
from iFactory.infrastructure.persistence.sqlalchemy.models import (
    StatusHistoryModel,
    MaterialInputHistoryModel,
)
from iFactory.infrastructure.persistence.sqlalchemy.mapper import SQLAlchemyMapper

logger = logging.getLogger(__name__)


class SqlAlchemyProductionRepository(ProductionRepository):
    """
    SQLAlchemy implementation of ProductionRepository.

    Handles all production history data persistence including:
    - Status history (device state changes over time)
    - Material input tracking
    - OEE metrics calculation
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ========================================================================
    # Status History - Single Device
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
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= window.start,
                    ),
                )
                .order_by(StatusHistoryModel.start_time)
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            periods = []
            for model in models:
                period = SQLAlchemyMapper.to_status_period(model)
                if period is not None:
                    periods.append(period)
            return periods
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
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= start_time,
                    ),
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

    # ========================================================================
    # Status History - Bulk Operations
    # ========================================================================

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
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= start_time,
                    ),
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
                if model.equip_code in grouped:
                    grouped[model.equip_code].append(record)

            return grouped
        except Exception as e:
            logger.error(f"Error getting bulk history: {e}")
            return {code.upper(): [] for code in equip_codes}

    async def get_all_device_history(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Sequence[HistoryRecord]]:
        """Get history for ALL devices in a time range."""
        try:
            stmt = (
                select(StatusHistoryModel)
                .where(
                    StatusHistoryModel.start_time <= end_time,
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= start_time,
                    ),
                )
                .order_by(
                    StatusHistoryModel.equip_code,
                    StatusHistoryModel.start_time,
                )
            )
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            # Group by equipment code
            grouped: Dict[str, List[HistoryRecord]] = defaultdict(list)

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

            return dict(grouped)
        except Exception as e:
            logger.error(f"Error getting all device history: {e}")
            return {}

    # ========================================================================
    # Status History - Persistence
    # ========================================================================

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
    ) -> int:
        """Bulk save multiple status periods."""
        if not periods:
            return 0

        try:
            models = [SQLAlchemyMapper.to_status_period_model(p, equip_name=equip_name) for p in periods]
            self._session.add_all(models)
            logger.debug(f"Bulk saved {len(periods)} status periods")
            return len(periods)
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

    async def delete_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> int:
        """Delete history records within a time range."""
        try:
            end_time = window.end or datetime.now()

            stmt = delete(StatusHistoryModel).where(
                StatusHistoryModel.equip_code == code.value,
                StatusHistoryModel.start_time >= window.start,
                StatusHistoryModel.start_time <= end_time,
            )
            result = await self._session.execute(stmt)
            deleted_count = result.rowcount

            logger.info(f"Deleted {deleted_count} history records for {code.value} " f"between {window.start} and {end_time}")
            return deleted_count
        except Exception as e:
            logger.error(f"Error deleting history for {code.value}: {e}")
            return 0

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

            inputs = []
            for model in models:
                material_input = SQLAlchemyMapper.to_material_input(model)
                if material_input is not None:
                    inputs.append(material_input)
            return inputs
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

    async def get_material_consumption(
        self,
        batch: str,
        window: Optional[TimeRange] = None,
    ) -> Sequence[MaterialInput]:
        """Get all consumption records for a material batch."""
        try:
            batch_upper = batch.upper().strip()

            conditions = [MaterialInputHistoryModel.material_batch == batch_upper]

            if window:
                end_time = window.end or datetime.now()
                conditions.extend(
                    [
                        MaterialInputHistoryModel.feeding_time >= window.start,
                        MaterialInputHistoryModel.feeding_time <= end_time,
                    ]
                )

            stmt = select(MaterialInputHistoryModel).where(and_(*conditions)).order_by(MaterialInputHistoryModel.feeding_time)
            result = await self._session.execute(stmt)
            models = result.scalars().all()

            inputs = []
            for model in models:
                material_input = SQLAlchemyMapper.to_material_input(model)
                if material_input is not None:
                    inputs.append(material_input)
            return inputs
        except Exception as e:
            logger.error(f"Error getting material consumption for batch {batch}: {e}")
            return []

    # ========================================================================
    # Statistics & Metrics
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
            window_end = window.end or now

            for period in periods:
                # Clamp to window boundaries
                start = max(period.start, window.start)
                end = min(period.end or now, window_end)

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
    ) -> OEEMetrics:
        """Calculate OEE metrics."""
        try:
            summary = await self.get_status_summary(code, window)

            total_time = window.duration_seconds
            if total_time <= 0:
                return OEEMetrics.empty()

            run_time = summary.get(MachineStatus.RUNNING, 0.0)

            # Calculate OEE using the dataclass method
            return OEEMetrics.calculate(
                planned_time=total_time,
                run_time=run_time,
                # For now, assume performance and quality are 100%
                # These would need production data to calculate properly
                theoretical_output=0,
                actual_output=0,
                good_output=0,
            )
        except Exception as e:
            logger.error(f"Error calculating OEE for {code.value}: {e}")
            return OEEMetrics.empty()

    async def get_downtime_summary(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> List[Tuple[str, float, int]]:
        """Get downtime summary grouped by reason code."""
        try:
            end_time = window.end or datetime.now()

            # Query with grouping by reason_code
            stmt = (
                select(
                    StatusHistoryModel.reason_code,
                    func.sum(
                        func.coalesce(
                            StatusHistoryModel.duration_seconds,
                            func.strftime("%s", func.coalesce(StatusHistoryModel.end_time, func.now()))
                            - func.strftime("%s", StatusHistoryModel.start_time),
                        )
                    ).label("total_seconds"),
                    func.count().label("occurrences"),
                )
                .where(
                    StatusHistoryModel.equip_code == code.value,
                    StatusHistoryModel.start_time <= end_time,
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= window.start,
                    ),
                    # Only count downtime statuses
                    StatusHistoryModel.equip_status.in_(
                        [
                            MachineStatus.STOPPED.value,
                            MachineStatus.SHUTDOWN.value,
                            MachineStatus.MAINTENANCE.value,
                            MachineStatus.ALARM.value,
                        ]
                    ),
                )
                .group_by(StatusHistoryModel.reason_code)
                .order_by(desc("total_seconds"))
            )

            result = await self._session.execute(stmt)
            rows = result.all()

            summary: List[Tuple[str, float, int]] = []
            for row in rows:
                reason = row.reason_code or "UNSPECIFIED"
                total_secs = float(row.total_seconds or 0)
                count = int(row.occurrences or 0)
                summary.append((reason, total_secs, count))

            return summary
        except Exception as e:
            logger.error(f"Error getting downtime summary for {code.value}: {e}")
            # Fallback: calculate from history
            return await self._calculate_downtime_fallback(code, window)

    async def _calculate_downtime_fallback(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> List[Tuple[str, float, int]]:
        """Fallback calculation for downtime summary."""
        try:
            periods = await self.get_status_history(code, window)

            # Group by reason code
            reason_data: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"total_seconds": 0.0, "count": 0})

            now = datetime.now()
            window_end = window.end or now

            for period in periods:
                if not period.status.implies_downtime:
                    continue

                # Clamp to window
                start = max(period.start, window.start)
                end = min(period.end or now, window_end)

                if end > start:
                    duration = (end - start).total_seconds()
                    reason = "UNSPECIFIED"  # StatusPeriod doesn't have reason_code
                    reason_data[reason]["total_seconds"] += duration
                    reason_data[reason]["count"] += 1

            result = [(reason, data["total_seconds"], data["count"]) for reason, data in reason_data.items()]
            result.sort(key=lambda x: x[1], reverse=True)
            return result
        except Exception as e:
            logger.error(f"Error in downtime fallback for {code.value}: {e}")
            return []

    # ========================================================================
    # Utility Methods
    # ========================================================================

    async def count_records(
        self,
        code: Optional[EquipmentCode] = None,
        window: Optional[TimeRange] = None,
    ) -> int:
        """Count history records."""
        try:
            conditions = []

            if code:
                conditions.append(StatusHistoryModel.equip_code == code.value)

            if window:
                end_time = window.end or datetime.now()
                conditions.append(StatusHistoryModel.start_time <= end_time)
                conditions.append(
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= window.start,
                    )
                )

            if conditions:
                stmt = select(func.count()).select_from(StatusHistoryModel).where(and_(*conditions))
            else:
                stmt = select(func.count()).select_from(StatusHistoryModel)

            result = await self._session.execute(stmt)
            count = result.scalar()
            return count or 0
        except Exception as e:
            logger.error(f"Error counting records: {e}")
            return 0

    async def get_distinct_devices(
        self,
        window: Optional[TimeRange] = None,
    ) -> List[str]:
        """Get list of distinct equipment codes with history."""
        try:
            conditions = []

            if window:
                end_time = window.end or datetime.now()
                conditions.append(StatusHistoryModel.start_time <= end_time)
                conditions.append(
                    or_(
                        StatusHistoryModel.end_time.is_(None),
                        StatusHistoryModel.end_time >= window.start,
                    )
                )

            if conditions:
                stmt = select(StatusHistoryModel.equip_code).where(and_(*conditions)).distinct().order_by(StatusHistoryModel.equip_code)
            else:
                stmt = select(StatusHistoryModel.equip_code).distinct().order_by(StatusHistoryModel.equip_code)

            result = await self._session.execute(stmt)
            codes = result.scalars().all()
            return list(codes)
        except Exception as e:
            logger.error(f"Error getting distinct devices: {e}")
            return []


__all__ = ["SqlAlchemyProductionRepository"]
