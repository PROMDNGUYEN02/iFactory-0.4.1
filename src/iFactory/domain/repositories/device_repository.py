# src/iFactory/domain/repositories/device_repository.py
"""
Device Repository Interface.

Abstract port for Device aggregate persistence.
"""

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

    This is the interface that the domain layer expects.
    Infrastructure layer provides the implementation.

    Provides both single-entity and bulk operations for efficiency.

    Usage (in application services):
        class SyncService:
            def __init__(self, device_repo: DeviceRepository):
                self._repo = device_repo

            async def sync_all(self):
                devices = await self._repo.get_all_as_dict()
                # ... sync logic
    """

    # ========================================================================
    # Single Entity Operations
    # ========================================================================

    @abstractmethod
    async def get_by_code(self, code: EquipmentCode) -> Optional[Device]:
        """
        Retrieve a single device by its code.

        Args:
            code: Equipment code

        Returns:
            Device if found, None otherwise
        """
        pass

    @abstractmethod
    async def save(self, device: Device) -> None:
        """
        Persist device state.

        For new devices, this creates the record.
        For existing devices, this updates the record.

        Args:
            device: Device to save
        """
        pass

    @abstractmethod
    async def delete(self, code: EquipmentCode) -> bool:
        """
        Remove a device from persistence.

        Args:
            code: Equipment code

        Returns:
            True if device was deleted, False if not found
        """
        pass

    @abstractmethod
    async def exists(self, code: EquipmentCode) -> bool:
        """
        Check if device exists.

        Args:
            code: Equipment code

        Returns:
            True if device exists
        """
        pass

    # ========================================================================
    # Bulk Read Operations
    # ========================================================================

    @abstractmethod
    async def get_all(self) -> Sequence[Device]:
        """
        Retrieve all registered devices.

        Returns:
            Sequence of all devices
        """
        pass

    @abstractmethod
    async def get_all_as_dict(self) -> Dict[str, Device]:
        """
        Retrieve all devices as a dictionary keyed by uppercase equipment code.

        Optimized for O(1) lookups during sync operations.

        Returns:
            Dictionary mapping equipment code (uppercase) to Device
        """
        pass

    @abstractmethod
    async def get_by_codes(self, codes: List[str]) -> Sequence[Device]:
        """
        Retrieve multiple devices by their codes in a single query.

        Args:
            codes: List of equipment codes (case-insensitive)

        Returns:
            Sequence of found devices (may be fewer than requested)
        """
        pass

    @abstractmethod
    async def get_by_codes_as_dict(self, codes: List[str]) -> Dict[str, Device]:
        """
        Retrieve multiple devices as a dictionary.

        Args:
            codes: List of equipment codes

        Returns:
            Dictionary mapping equipment code to Device
        """
        pass

    @abstractmethod
    async def get_active(self) -> Sequence[Device]:
        """
        Retrieve only active devices (not shutdown/unknown).

        Returns:
            Sequence of active devices
        """
        pass

    @abstractmethod
    async def get_by_status(self, status: int) -> Sequence[Device]:
        """
        Retrieve devices with specific status.

        Args:
            status: MachineStatus value

        Returns:
            Sequence of devices with that status
        """
        pass

    @abstractmethod
    async def get_dashboard_snapshot(
        self,
    ) -> Sequence[Tuple[Device, Optional[MaterialInput]]]:
        """
        Retrieve a rich snapshot of all devices including their
        latest material input (if available).

        Optimized for dashboard display with a single query.

        Returns:
            Sequence of (Device, MaterialInput or None) tuples
        """
        pass

    # ========================================================================
    # Bulk Write Operations
    # ========================================================================

    @abstractmethod
    async def bulk_save(self, devices: List[Device]) -> None:
        """
        Persist multiple devices in a single batch operation.

        More efficient than individual saves for large updates.

        Args:
            devices: List of devices to save
        """
        pass

    @abstractmethod
    async def bulk_upsert(self, devices: List[Device]) -> Tuple[int, int]:
        """
        Insert or update multiple devices.

        Args:
            devices: List of devices to upsert

        Returns:
            Tuple of (inserted_count, updated_count)
        """
        pass

    # ========================================================================
    # Statistics
    # ========================================================================

    @abstractmethod
    async def count(self) -> int:
        """
        Count total devices.

        Returns:
            Number of devices in repository
        """
        pass

    @abstractmethod
    async def count_by_status(self) -> Dict[int, int]:
        """
        Count devices by status.

        Returns:
            Dictionary mapping status value to count
        """
        pass

    # ========================================================================
    # Availability/History Calculation
    # ========================================================================

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
