from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.time_range import TimeRange
from ..value_objects.status_period import StatusPeriod
from ..value_objects.material_input import MaterialInput


class DeviceRepository(ABC):
    """Interface for managing Device aggregates."""

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]: ...

    @abstractmethod
    async def get_all(self) -> Sequence[Device]: ...

    @abstractmethod
    async def save(self, device: Device) -> None: ...


class StatusRepository(ABC):
    """Interface for querying and persisting historical Status Periods."""

    @abstractmethod
    async def get_latest(self, code: EquipmentCode) -> Optional[StatusPeriod]: ...

    @abstractmethod
    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[StatusPeriod]: ...

    @abstractmethod
    async def save_period(self, period: StatusPeriod) -> None: ...


class InputRepository(ABC):
    """Interface for managing material input events."""

    @abstractmethod
    async def get_latest(self, code: EquipmentCode) -> Optional[MaterialInput]: ...

    @abstractmethod
    async def get_history(self, code: EquipmentCode, window: TimeRange) -> Sequence[MaterialInput]: ...

    @abstractmethod
    async def save(self, record: MaterialInput) -> None: ...
