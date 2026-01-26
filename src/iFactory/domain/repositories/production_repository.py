from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.time_range import TimeRange
from ..value_objects.status_period import StatusPeriod
from ..value_objects.material_input import MaterialInput


class ProductionRepository(ABC):
    """
    Abstract interface for querying and persisting historical production logs.
    Handles Status Periods and Material Inputs.
    """

    @abstractmethod
    async def get_latest_status(self, code: EquipmentCode) -> Optional[StatusPeriod]:
        pass

    @abstractmethod
    async def get_status_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]:
        pass

    @abstractmethod
    async def save_status_period(self, period: StatusPeriod) -> None:
        pass

    @abstractmethod
    async def get_latest_input(self, code: EquipmentCode) -> Optional[MaterialInput]:
        pass

    @abstractmethod
    async def get_input_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]:
        pass

    @abstractmethod
    async def save_material_input(self, record: MaterialInput) -> None:
        pass
