from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence
from ..value_objects.material_input import MaterialInput
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.time_range import TimeRange


class InputRepository(ABC):
    @abstractmethod
    async def get_latest(self, code: EquipmentCode) -> Optional[MaterialInput]: ...
    @abstractmethod
    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]: ...
    @abstractmethod
    async def save(self, record: MaterialInput) -> None: ...
