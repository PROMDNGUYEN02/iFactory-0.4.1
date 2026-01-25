from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence
from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode


class DeviceRepository(ABC):
    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]: ...
    @abstractmethod
    async def get_all(self) -> Sequence[Device]: ...
    @abstractmethod
    async def save(self, device: Device) -> None: ...
    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool: ...
