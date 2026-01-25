from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, Optional, Sequence

from ..value_objects.device_history import DeviceHistory
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status
from ..value_objects.time_range import TimeRange


class StatusRepository(ABC):
    @abstractmethod
    async def get_latest(self, code: str | EquipmentCode) -> Optional[DeviceHistory]:
        pass

    @abstractmethod
    async def get_all_latest(self, codes: Optional[Sequence[EquipmentCode]] = None) -> Sequence[DeviceHistory]:
        pass

    @abstractmethod
    async def get_history(self, code: EquipmentCode, time_range: TimeRange) -> Sequence[DeviceHistory]:
        pass

    @abstractmethod
    async def get_history_for_codes(self, codes: Sequence[EquipmentCode], time_range: TimeRange) -> Dict[str, Sequence[DeviceHistory]]:
        pass

    @abstractmethod
    async def get_by_status(self, status: Status, time_range: TimeRange | None = None) -> Sequence[DeviceHistory]:
        pass

    @abstractmethod
    async def save_latest(self, period: DeviceHistory) -> None:
        pass

    @abstractmethod
    async def save_to_history(self, period: DeviceHistory) -> None:
        pass

    @abstractmethod
    async def delete_history_before(self, cutoff: datetime) -> int:
        pass
