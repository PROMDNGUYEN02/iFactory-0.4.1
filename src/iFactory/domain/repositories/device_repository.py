from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode


class DeviceRepository(ABC):
    """
    Abstract interface for managing Device Aggregates.
    Only speaks Domain Language. Must NOT leak infrastructure dependencies (SQL, JSON, HTTP).
    """

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """Retrieves a single Device aggregate by its equipment code."""
        pass

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        """Retrieves all Device aggregates."""
        pass

    @abstractmethod
    async def save(self, device: Device) -> None:
        """Persists the Device aggregate and handles event dispatching."""
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        """Removes a Device aggregate from the system."""
        pass
