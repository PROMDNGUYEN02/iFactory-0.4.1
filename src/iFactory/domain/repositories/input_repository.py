"""
Input repository interface - Contract for material input data access.

This interface defines how application accesses material input
data for production tracking and reporting.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional, Sequence, TYPE_CHECKING

from ..value_objects.material_input import MaterialInput
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.time_range import TimeRange

if TYPE_CHECKING:
    pass

__all__ = ["InputRepository"]


class InputRepository(ABC):
    """
    Abstract repository for material input persistence.

    Handles both:
        - Latest input (hot store) for quick access
        - Input history (cold store) for reporting

    Contract:
        - All methods are async (non-blocking for Qt GUI)
        - Input uses Value Objects (type-safe)
        - Returns Domain entities (not DTOs, not ORM models)
    """

    # ====== QUERIES ======

    @abstractmethod
    async def get_latest(
        self,
        code: EquipmentCode
    ) -> Optional[MaterialInput]:
        """
        Get latest material input for a device.

        Args:
            code: Equipment code

        Returns:
            Latest input or None
        """
        pass

    @abstractmethod
    async def get_all_latest(
        self,
        codes: Optional[Sequence[EquipmentCode]] = None
    ) -> Sequence[MaterialInput]:
        """
        Get latest input for all devices (or filtered).

        Args:
            codes: Optional filter by equipment codes

        Returns:
            Sequence of latest inputs
        """
        pass

    @abstractmethod
    async def get_history(
        self,
        code: EquipmentCode,
        time_range: TimeRange
    ) -> Sequence[MaterialInput]:
        """
        Get input history for a device in time range.

        Args:
            code: Equipment code
            time_range: Time range to query

        Returns:
            Sequence of inputs in chronological order
        """
        pass

    @abstractmethod
    async def get_history_for_codes(
        self,
        codes: Sequence[EquipmentCode],
        time_range: TimeRange
    ) -> dict[str, Sequence[MaterialInput]]:
        """
        Get input history for multiple devices.

        Args:
            codes: Equipment codes (Value Objects)
            time_range: Time range to query

        Returns:
            Dictionary mapping equipment code to input sequences
        """
        pass

    @abstractmethod
    async def get_history_for_codes(
        self,
        codes: Sequence[EquipmentCode],
        time_range: TimeRange
    ) -> dict[str, Sequence[MaterialInput]]:
        """
        Get input history for multiple devices.

        Args:
            codes: Equipment codes (Value Objects)
            time_range: Time range to query

        Returns:
            Dictionary mapping equipment code to input sequences
        """
        pass

    # ====== COMMANDS ======

    @abstractmethod
    async def save_latest(
        self,
        input_record: MaterialInput
    ) -> None:
        """
        Save/update latest input for a device.

        Args:
            input_record: Input to save

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def save_latest_many(
        self,
        inputs: Sequence[MaterialInput]
    ) -> int:
        """
        Save/update latest input for multiple devices.

        Args:
            inputs: Inputs to save

        Returns:
            Number of records saved

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def save_to_history(
        self,
        input_record: MaterialInput
    ) -> None:
        """
        Archive input to history.

        Args:
            input_record: Input to archive

        Raises:
            RepositoryError: If save fails
        """
        pass

    @abstractmethod
    async def save_many_to_history(
        self,
        inputs: Sequence[MaterialInput]
    ) -> int:
        """
        Archive multiple inputs to history.

        Args:
            inputs: Inputs to archive

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

        Args:
            cutoff: Delete records before this time

        Returns:
            Number of records deleted

        Raises:
            RepositoryError: If delete fails
        """
        pass
