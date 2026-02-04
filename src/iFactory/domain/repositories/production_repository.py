# src/iFactory/domain/repositories/production_repository.py
"""
Production Repository Interface.

Abstract port for production history persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence

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
    """

    equipment_code: str
    status: int
    start_time: datetime
    end_time: Optional[datetime]
    equip_name: Optional[str] = None
    reason_code: Optional[str] = None

    @property
    def status_enum(self) -> MachineStatus:
        """Get status as MachineStatus enum."""
        return MachineStatus(self.status)

    @property
    def duration_seconds(self) -> float:
        """Get duration in seconds."""
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

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
        }


class ProductionRepository(ABC):
    """
    Abstract Port interface for querying and persisting production history.

    Strictly uses Domain Value Objects for inputs and outputs.

    This repository handles:
    - Status history (periods of each status)
    - Material input tracking
    - Production metrics

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
    # Status History
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
            Sequence of HistoryRecord objects
        """
        pass

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
    ) -> None:
        """
        Bulk save multiple status periods at once.

        More efficient than individual saves.

        Args:
            periods: List of StatusPeriod to save
            equip_name: Optional equipment name (applied to all)
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
            Sequence of MaterialInput objects
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

    # ========================================================================
    # Statistics
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
    ) -> Dict[str, float]:
        """
        Calculate OEE (Overall Equipment Effectiveness) metrics.

        Args:
            code: Equipment code
            window: Time range to analyze

        Returns:
            Dictionary with keys: availability, performance, quality, oee
        """
        pass


__all__ = ["ProductionRepository", "HistoryRecord"]
