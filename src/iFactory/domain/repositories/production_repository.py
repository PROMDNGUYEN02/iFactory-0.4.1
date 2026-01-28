from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.material_input import MaterialInput
from ..value_objects.status_period import StatusPeriod
from ..value_objects.time_range import TimeRange


class ProductionRepository(ABC):
    """
    Abstract Port interface for querying and persisting production history.
    Strictly uses Domain Value Objects for inputs and outputs.
    """

    @abstractmethod
    async def get_latest_status(
        self,
        code: EquipmentCode,
    ) -> Optional[StatusPeriod]:
        """Get the most recent status period recorded for a device."""
        pass

    @abstractmethod
    async def get_status_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[StatusPeriod]:
        """Get all status periods overlapping the specified time window."""
        pass

    @abstractmethod
    async def save_status_period(self, period: StatusPeriod) -> None:
        """Record a completed or ongoing status period."""
        pass

    @abstractmethod
    async def get_latest_input(
        self,
        code: EquipmentCode,
    ) -> Optional[MaterialInput]:
        """Get the most recent material input for a device."""
        pass

    @abstractmethod
    async def get_input_history(
        self,
        code: EquipmentCode,
        window: TimeRange,
    ) -> Sequence[MaterialInput]:
        """Get material inputs recorded during the specified time window."""
        pass

    @abstractmethod
    async def save_material_input(self, record: MaterialInput) -> None:
        """Persist a material input record."""
        pass
