"""
Remote Data Source Port.
Interface for external data sources (MSSQL, API, etc.)
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class IRemoteDataSource(ABC):
    """Port interface for remote data sources."""

    @abstractmethod
    async def fetch_latest_status(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest status for specified devices.
        If equipment_codes is None, fetch all devices.
        """
        pass

    @abstractmethod
    async def fetch_device_status(
        self,
        equip_code: str,
        days: int = 30,
    ) -> List[Dict[str, Any]]:
        """Fetch history status for a single device."""
        pass

    @abstractmethod
    async def fetch_device_history_range(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch history for a specific time range."""
        pass

    @abstractmethod
    async def fetch_latest_history_records(
        self,
        equip_code: str,
        limit: int = 2,
    ) -> List[Dict[str, Any]]:
        """
        Fetch the N most recent history records for a device.
        Used for incremental sync (upsert).
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """Clean up resources."""
        pass


__all__ = ["IRemoteDataSource"]
