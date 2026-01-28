from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode


class DeviceRepository(ABC):
    """
    Abstract Port interface for managing Device Aggregates.
    """

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """Retrieve a device by its unique equipment code."""
        pass

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        """Retrieve all registered devices."""
        pass

    @abstractmethod
    async def get_active(self) -> Sequence[Device]:
        """Retrieve devices that are currently in an active state."""
        pass

    @abstractmethod
    async def save(self, device: Device) -> None:
        """Persist the current state of a device aggregate."""
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        """Remove a device from the system. Returns True if deleted."""
        pass

    @abstractmethod
    async def exists(self, code: EquipmentCode) -> bool:
        """Check if a device exists by code."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Return total number of registered devices."""
        pass
