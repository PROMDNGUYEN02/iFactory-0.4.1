# File: domain/repositories/device_repository.py
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Sequence, Tuple

from ..entities.device import Device
from ..value_objects.equipment_code import EquipmentCode
from ..value_objects.material_input import MaterialInput


class DeviceRepository(ABC):
    """
    Abstract Port for Device Aggregate access.

    Provides both single-entity and bulk operations for efficiency.
    """

    # --- Single Entity Operations ---

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """Retrieve a single device by its code."""
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

    # --- Bulk Read Operations ---

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        """Retrieve all registered devices."""
        pass

    @abstractmethod
    async def get_all_as_dict(self) -> Dict[str, Device]:
        """
        Retrieve all devices as a dictionary keyed by uppercase equipment code.
        Optimized for O(1) lookups during sync operations.
        """
        pass

    @abstractmethod
    async def get_by_codes(self, codes: List[str]) -> Sequence[Device]:
        """Retrieve multiple devices by their codes in a single query."""
        pass

    @abstractmethod
    async def get_by_codes_as_dict(self, codes: List[str]) -> Dict[str, Device]:
        """Retrieve multiple devices as a dictionary."""
        pass

    @abstractmethod
    async def get_active(self) -> Sequence[Device]:
        """Retrieve only active devices."""
        pass

    @abstractmethod
    async def get_dashboard_snapshot(
        self,
    ) -> Sequence[Tuple[Device, Optional[MaterialInput]]]:
        """
        Retrieve a rich snapshot of all devices including their
        latest material input (if available).
        Optimized for dashboard display.
        """
        pass

    # --- Bulk Write Operations ---

    @abstractmethod
    async def bulk_save(self, devices: List[Device]) -> None:
        """
        Persist multiple devices in a single batch operation.
        More efficient than individual saves for large updates.
        """
        pass

    # --- Statistics ---

    @abstractmethod
    async def count(self) -> int:
        """Count total devices."""
        pass

    # --- Availability Calculation ---

    @abstractmethod
    async def get_today_run_time(self, code: str) -> float:
        """
        Get total RUN time (in seconds) for a device from 00:00 today until now.

        Args:
            code: Equipment code (uppercase)

        Returns:
            Total seconds the device was in RUNNING status today
        """
        pass

    @abstractmethod
    async def get_today_run_time_bulk(self, codes: List[str]) -> Dict[str, float]:
        """
        Get total RUN time for multiple devices in a single query.

        Args:
            codes: List of equipment codes

        Returns:
            Dictionary mapping equipment code to run time in seconds
        """
        pass


__all__ = ["DeviceRepository"]
