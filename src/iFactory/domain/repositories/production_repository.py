# src/iFactory/domain/repositories/production_repository.py
"""
Production Repository Interface.

Abstract port for production history persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Sequence, Tuple

from ..enums.machine_status import MachineStatus
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.material_input import MaterialInput
from ..value_objects.status_period import StatusPeriod
from ..value_objects.time_range import TimeRange


@dataclass(frozen=True)
class HistoryRecord:
    """
    Represents a single history record from storage.

    This is a simple DTO for transferring history data
    between layers without domain logic.

    Usage:
        record = HistoryRecord(
            equipment_code="CNC-001",
            status=1,  # RUNNING
            start_time=datetime(2024, 1, 15, 8, 0),
            end_time=datetime(2024, 1, 15, 12, 0),
        )

        # Convert to domain value object
        period = record.to_status_period()
    """

    equipment_code: str
    status: int
    start_time: datetime
    end_time: Optional[datetime] = None
    equip_name: Optional[str] = None
    reason_code: Optional[str] = None

    @property
    def status_enum(self) -> MachineStatus:
        """Get status as MachineStatus enum."""
        return MachineStatus.from_value(self.status)

    @property
    def is_ongoing(self) -> bool:
        """True if this record has no end time."""
        return self.end_time is None

    @property
    def duration_seconds(self) -> float:
        """
        Get duration in seconds.

        For ongoing records, calculates until now.
        """
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def duration_minutes(self) -> float:
        """Get duration in minutes."""
        return self.duration_seconds / 60.0

    @property
    def duration_hours(self) -> float:
        """Get duration in hours."""
        return self.duration_seconds / 3600.0

    def to_status_period(self) -> StatusPeriod:
        """Convert to StatusPeriod value object."""
        return StatusPeriod.create(
            equipment_code=self.equipment_code,
            status=self.status,
            start=self.start_time,
            end=self.end_time,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "equipment_code": self.equipment_code,
            "status": self.status,
            "status_name": self.status_enum.name,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "equip_name": self.equip_name,
            "reason_code": self.reason_code,
            "duration_seconds": self.duration_seconds,
            "is_ongoing": self.is_ongoing,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoryRecord":
        """Deserialize from dictionary."""
        return cls(
            equipment_code=data["equipment_code"],
            status=data["status"],
            start_time=(datetime.fromisoformat(data["start_time"]) if isinstance(data["start_time"], str) else data["start_time"]),
            end_time=(
                datetime.fromisoformat(data["end_time"]) if data.get("end_time") and isinstance(data["end_time"], str) else data.get("end_time")
            ),
            equip_name=data.get("equip_name"),
            reason_code=data.get("reason_code"),
        )


@dataclass(frozen=True)
class OEEMetrics:
    """
    OEE (Overall Equipment Effectiveness) metrics.

    OEE = Availability × Performance × Quality

    Attributes:
        availability: Ratio of actual run time to planned production time
        performance: Ratio of actual output to theoretical output
        quality: Ratio of good output to total output
        oee: Overall effectiveness (product of above three)
        planned_time_seconds: Total planned production time
        run_time_seconds: Actual running time
        downtime_seconds: Total downtime
    """

    availability: float
    performance: float
    quality: float
    oee: float
    planned_time_seconds: float = 0.0
    run_time_seconds: float = 0.0
    downtime_seconds: float = 0.0

    @classmethod
    def calculate(
        cls,
        planned_time: float,
        run_time: float,
        theoretical_output: int = 0,
        actual_output: int = 0,
        good_output: int = 0,
    ) -> "OEEMetrics":
        """
        Calculate OEE metrics from raw data.

        Args:
            planned_time: Planned production time in seconds
            run_time: Actual running time in seconds
            theoretical_output: Maximum possible output
            actual_output: Actual units produced
            good_output: Good units (no defects)
        """
        # Availability
        availability = run_time / planned_time if planned_time > 0 else 0.0

        # Performance (simplified - assumes 100% if no output data)
        if theoretical_output > 0 and actual_output > 0:
            performance = actual_output / theoretical_output
        else:
            performance = 1.0 if run_time > 0 else 0.0

        # Quality (simplified - assumes 100% if no quality data)
        if actual_output > 0 and good_output > 0:
            quality = good_output / actual_output
        else:
            quality = 1.0 if run_time > 0 else 0.0

        # OEE
        oee = availability * performance * quality

        return cls(
            availability=min(1.0, max(0.0, availability)),
            performance=min(1.0, max(0.0, performance)),
            quality=min(1.0, max(0.0, quality)),
            oee=min(1.0, max(0.0, oee)),
            planned_time_seconds=planned_time,
            run_time_seconds=run_time,
            downtime_seconds=max(0, planned_time - run_time),
        )

    def to_dict(self) -> Dict[str, float]:
        """Serialize to dictionary with percentage values."""
        return {
            "availability": round(self.availability * 100, 2),
            "performance": round(self.performance * 100, 2),
            "quality": round(self.quality * 100, 2),
            "oee": round(self.oee * 100, 2),
            "planned_time_seconds": self.planned_time_seconds,
            "run_time_seconds": self.run_time_seconds,
            "downtime_seconds": self.downtime_seconds,
        }


class ProductionRepository(ABC):
    """
    Abstract Port interface for querying and persisting production history.

    Strictly uses Domain Value Objects for inputs and outputs.

    This repository handles:
    - Status history (periods of each status)
    - Material input tracking
    - Production metrics (OEE)

    Usage:
        class HistoryService:
            def __init__(self, prod_repo: ProductionRepository):
                self._repo = prod_repo

            async def get_downtime_report(self, code: str, date: date):
                window = TimeRange.for_date(date)
                periods = await self._repo.get_status_history(
                    EquipmentCode.create(code),
                    window
                )
                return [p for p in periods if p.is_downtime]
    """

    # ========================================================================
    # Status History - Single Device
    # ========================================================================

    @abstractmethod
    async def get_latest_status(
        self,
        code: EquipmentCode,
    ) -> Optional[StatusPeriod]:
        """
        Get the most recent status period recorded for a device.

        Args:
            code: Equipment code

        Returns:
            Latest StatusPeriod or None if no history
        """
        pass

    @abstractmethod
    async def get_status_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[StatusPeriod]:
        """
        Get all status periods overlapping the specified time window.

        Args:
            code: Equipment code
            window: Time range to query

        Returns:
            Sequence of StatusPeriod objects ordered by start time
        """
        pass

    @abstractmethod
    async def get_history(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> Sequence[HistoryRecord]:
        """
        Get history records for a device within a time range.

        Simplified interface that accepts primitive types.

        Args:
            equip_code: Equipment code string
            start_time: Start of range
            end_time: End of range

        Returns:
            Sequence of HistoryRecord objects ordered by start_time
        """
        pass

    # ========================================================================
    # Status History - Bulk Operations
    # ========================================================================

    @abstractmethod
    async def get_history_bulk(
        self,
        equip_codes: List[str],
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Sequence[HistoryRecord]]:
        """
        Get history records for multiple devices in a single query.

        Args:
            equip_codes: List of equipment codes
            start_time: Start of range
            end_time: End of range

        Returns:
            Dictionary mapping equipment code to history records
        """
        pass

    @abstractmethod
    async def get_all_device_history(
        self,
        start_time: datetime,
        end_time: datetime,
    ) -> Dict[str, Sequence[HistoryRecord]]:
        """
        Get history for ALL devices in a time range.

        Useful for dashboard/reporting.

        Args:
            start_time: Start of range
            end_time: End of range

        Returns:
            Dictionary mapping equipment code to history records
        """
        pass

    # ========================================================================
    # Status History - Persistence
    # ========================================================================

    @abstractmethod
    async def save_status_period(
        self,
        period: StatusPeriod,
        equip_name: Optional[str] = None,
    ) -> None:
        """
        Record a single status period.

        Args:
            period: StatusPeriod to save
            equip_name: Optional equipment name
        """
        pass

    @abstractmethod
    async def bulk_save_status_history(
        self,
        periods: List[StatusPeriod],
        equip_name: Optional[str] = None,
    ) -> int:
        """
        Bulk save multiple status periods at once.

        More efficient than individual saves.

        Args:
            periods: List of StatusPeriod to save
            equip_name: Optional equipment name (applied to all)

        Returns:
            Number of periods saved
        """
        pass

    @abstractmethod
    async def close_open_period(
        self,
        code: EquipmentCode,
        end_time: datetime,
    ) -> bool:
        """
        Close any open (ongoing) period for a device.

        Args:
            code: Equipment code
            end_time: Time to close the period

        Returns:
            True if a period was closed, False if no open period
        """
        pass

    @abstractmethod
    async def delete_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> int:
        """
        Delete history records within a time range.

        Use with caution!

        Args:
            code: Equipment code
            window: Time range to delete

        Returns:
            Number of records deleted
        """
        pass

    # ========================================================================
    # Material Input
    # ========================================================================

    @abstractmethod
    async def get_latest_input(
        self,
        code: EquipmentCode,
    ) -> Optional[MaterialInput]:
        """
        Get the most recent material input for a device.

        Args:
            code: Equipment code

        Returns:
            Latest MaterialInput or None
        """
        pass

    @abstractmethod
    async def get_input_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[MaterialInput]:
        """
        Get material inputs recorded during the specified time window.

        Args:
            code: Equipment code
            window: Time range to query

        Returns:
            Sequence of MaterialInput objects ordered by feeding_time
        """
        pass

    @abstractmethod
    async def save_material_input(self, record: MaterialInput) -> None:
        """
        Persist a material input record.

        Args:
            record: MaterialInput to save
        """
        pass

    @abstractmethod
    async def get_material_consumption(
        self,
        batch: str,
        window: Optional[TimeRange] = None,
    ) -> Sequence[MaterialInput]:
        """
        Get all consumption records for a material batch.

        Useful for traceability.

        Args:
            batch: Material batch identifier
            window: Optional time range filter

        Returns:
            Sequence of MaterialInput records
        """
        pass

    # ========================================================================
    # Statistics & Metrics
    # ========================================================================

    @abstractmethod
    async def get_status_summary(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Dict[MachineStatus, float]:
        """
        Get summary of time spent in each status.

        Args:
            code: Equipment code
            window: Time range to analyze

        Returns:
            Dictionary mapping status to total seconds
        """
        pass

    @abstractmethod
    async def get_oee_metrics(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> OEEMetrics:
        """
        Calculate OEE (Overall Equipment Effectiveness) metrics.

        Args:
            code: Equipment code
            window: Time range to analyze

        Returns:
            OEEMetrics dataclass with availability, performance, quality, oee
        """
        pass

    @abstractmethod
    async def get_downtime_summary(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> List[Tuple[str, float, int]]:
        """
        Get downtime summary grouped by reason code.

        Args:
            code: Equipment code
            window: Time range to analyze

        Returns:
            List of (reason_code, total_seconds, occurrence_count) tuples
        """
        pass

    # ========================================================================
    # Utility Methods
    # ========================================================================

    @abstractmethod
    async def count_records(
        self,
        code: Optional[EquipmentCode] = None,
        window: Optional[TimeRange] = None,
    ) -> int:
        """
        Count history records.

        Args:
            code: Optional equipment code filter
            window: Optional time range filter

        Returns:
            Number of matching records
        """
        pass

    @abstractmethod
    async def get_distinct_devices(
        self,
        window: Optional[TimeRange] = None,
    ) -> List[str]:
        """
        Get list of distinct equipment codes with history.

        Args:
            window: Optional time range filter

        Returns:
            List of equipment codes
        """
        pass


__all__ = [
    "ProductionRepository",
    "HistoryRecord",
    "OEEMetrics",
]
