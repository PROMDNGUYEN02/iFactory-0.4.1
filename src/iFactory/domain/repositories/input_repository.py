from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Sequence

from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.material_input import MaterialInput
from ..value_objects.time_range import TimeRange


class InputRepository(ABC):
    @abstractmethod
    async def get_latest(self, code: EquipmentCode) -> Optional[MaterialInput]:
        pass

    @abstractmethod
    async def get_all_latest(self, codes: Optional[Sequence[EquipmentCode]] = None) -> Sequence[MaterialInput]:
        pass

    @abstractmethod
    async def get_history(self, code: EquipmentCode, time_range: TimeRange) -> Sequence[MaterialInput]:
        pass

    @abstractmethod
    async def get_history_for_codes(self, codes: Sequence[EquipmentCode], time_range: TimeRange) -> Dict[str, Sequence[MaterialInput]]:
        pass

    @abstractmethod
    async def save_latest(self, input_record: MaterialInput) -> None:
        pass

    @abstractmethod
    async def save_to_history(self, input_record: MaterialInput) -> None:
        pass

    @abstractmethod
    async def delete_history_before(self, cutoff: datetime) -> int:
        pass
