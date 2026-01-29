from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional, Sequence, Tuple

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.material_input import MaterialInput


class DeviceRepository(ABC):
    """
    Abstract Port for Device Aggregate access.
    """

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """Retrieve a single device by its code."""
        pass

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        """Retrieve all registered devices."""
        pass

    @abstractmethod
    async def get_dashboard_snapshot(self) -> Sequence[Tuple[Device, Optional[MaterialInput]]]:
        """
        Retrieve a rich snapshot of all devices including their
        latest material input (if available).
        Optimized for dashboard display.
        """
        pass

    @abstractmethod
    async def get_active(self) -> Sequence[Device]:
        """Retrieve only active devices."""
        pass

    @abstractmethod
    async def save(self, device: Device) -> None:
        """Persist device state."""
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        """Remove a device."""
        pass

    @abstractmethod
    async def exists(self, code: EquipmentCode) -> bool:
        """Check if device exists."""
        pass

    @abstractmethod
    async def count(self) -> int:
        """Count total devices."""
        pass
