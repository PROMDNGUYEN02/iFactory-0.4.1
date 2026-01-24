"""
Status repository interface - Contract for status history access.

This interface defines how application accesses device status
history for Gantt charts and reporting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence, TYPE_CHECKING

from ..value_objects.device_history import DeviceHistory
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.time_range import TimeRange
from ..value_objects.status import Status

if TYPE_CHECKING:
    pass

__all__ = ["StatusRepository"]


class StatusRepository(ABC):
    """
    Abstract repository for status history persistence.

    Handles both:
        - Latest status (hot store) for quick access
        - Status history (cold store) for reporting/Gantt

    Contract:
        - All methods are async (non-blocking for Qt GUI)
        - Input uses Value Objects (type-safe)
        - Returns Domain entities (not DTOs, not ORM models)
    """

    # ====== QUERIES ======

    @abstractmethod
    async def get_latest(
        self,
        code: str | EquipmentCode
    ) -> Optional[DeviceHistory]:
        """
        Get latest status period for a device.

        Args:
            code: Equipment code

        Returns:
            Latest status period or None
        """
        pass

    @abstractmethod
    async def get_all_latest(
        self,
        codes: Optional[Sequence[EquipmentCode]] = None
    ) -> Sequence[DeviceHistory]:
        """
        Get latest status for all devices (or filtered).

        Args:
            codes: Optional filter by equipment codes

        Returns:
            Sequence of latest status periods
        """
        pass

    @abstractmethod
    async def get_history(
        self,
        code: EquipmentCode,
        time_range: TimeRange
    ) -> Sequence[DeviceHistory]:
        """
        Get status history for a device in time range.

        Args:
            code: Equipment code
            time_range: Time range to query

        Returns:
            Sequence of status periods in chronological order
        """
        pass

    @abstractmethod
    async def get_history_for_codes(
        self,
        codes: Sequence[EquipmentCode],
        time_range: TimeRange
    ) -> dict[str, Sequence[DeviceHistory]]:
        """
        Get status history for multiple devices.

        Args:
            codes: Equipment codes (Value Objects)
            time_range: Time range to query

        Returns:
            Dictionary mapping equipment code to status periods
        """
        pass

    @abstractmethod
    async def get_by_status(
        self,
        status: "Status",
        time_range: TimeRange | None = None
    ) -> Sequence[DeviceHistory]:
        """
        Get status periods with specific status.

        Args:
            status: Status Value Object
            time_range: Optional time range filter

        Returns:
            Sequence of status periods
        """
        pass

    @abstractmethod
    async def get_status_duration(
        self,
        code: EquipmentCode,
        status: "Status",
        time_range: TimeRange
    ) -> float:
        """
        Get total duration of a status in time range.

        Args:
            code: Equipment code
            status: Status Value Object
            time_range: Time range to query

        Returns:
            Total duration in seconds
        """
        pass

    @abstractmethod
    async def get_status_summary(
        self,
        code: EquipmentCode,
        time_range: TimeRange
    ) -> dict[str, float]:
        """
        Get duration summary for all statuses.

        Args:
            code: Equipment code
            time_range: Time range to query

        Returns:
            Dictionary mapping status name to total seconds
        """
        pass

    # ====== COMMANDS ======

    @abstractmethod
    async def save_latest(self, period: DeviceHistory) -> None:
        """
        Save/update latest status for a device.

        Args:
            period: Status period to save

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def save_latest_many(
        self,
        periods: Sequence[DeviceHistory]
    ) -> int:
        """
        Save/update latest status for multiple devices.

        Args:
            periods: Status periods to save

        Returns:
            Number of records saved

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def save_to_history(self, period: DeviceHistory) -> None:
        """
        Archive status period to history.

        Args:
            period: Status period to archive

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def save_many_to_history(
        self,
        periods: Sequence[DeviceHistory]
    ) -> int:
        """
        Archive multiple status periods to history.

        Args:
            periods: Status periods to archive

        Returns:
            Number of records archived

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def delete_history_before(
        self,
        cutoff: datetime
    ) -> int:
        """
        Delete history records before cutoff date.

        Used for data retention policies.

        Args:
            cutoff: Delete records before this time

        Returns:
            Number of records deleted

        Raises:
            RepositoryError: If delete fails
        """
        pass
