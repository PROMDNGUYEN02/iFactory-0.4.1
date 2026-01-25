from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.status import Status


class DeviceRepository(ABC):
    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        pass

    @abstractmethod
    async def get_by_codes(self, codes: Sequence[str]) -> Sequence[Device]:
        pass

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        pass

    @abstractmethod
    async def get_by_status(self, status: Status) -> Sequence[Device]:
        pass

    @abstractmethod
    async def exists(self, code: EquipmentCode) -> bool:
        pass

    @abstractmethod
    async def count(self) -> int:
        pass

    @abstractmethod
    async def save(self, device: Device) -> None:
        pass

    @abstractmethod
    async def save_many(self, devices: Sequence[Device]) -> int:
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        pass
