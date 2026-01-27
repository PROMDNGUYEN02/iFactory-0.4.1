from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode


class DeviceRepository(ABC):
    """
    Abstract interface for managing Device Aggregates.

    Pure domain interface expressed in business language.
    Independent of storage mechanisms.
    """

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        pass

    @abstractmethod
    async def get_by_code_string(self, code: str) -> Optional[Device]:
        pass

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        pass

    @abstractmethod
    async def get_active(self) -> Sequence[Device]:
        pass

    @abstractmethod
    async def save(self, device: Device) -> None:
        pass

    @abstractmethod
    async def save_many(self, devices: Sequence[Device]) -> None:
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        pass

    @abstractmethod
    async def exists(self, code: EquipmentCode) -> bool:
        pass

    @abstractmethod
    async def count(self) -> int:
        pass
