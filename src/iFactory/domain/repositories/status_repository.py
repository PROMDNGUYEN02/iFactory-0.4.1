from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Dict, Optional, Sequence
from ..value_objects.status_period import StatusPeriod
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.time_range import TimeRange


class StatusRepository(ABC):
    @abstractmethod
    async def get_latest(self, code: EquipmentCode) -> Optional[StatusPeriod]: ...
    @abstractmethod
    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]: ...
    @abstractmethod
    async def save_period(self, period: StatusPeriod) -> None: ...
