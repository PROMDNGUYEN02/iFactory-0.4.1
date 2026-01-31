# File: application/ports/remote.py
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, List, Optional


class IRemoteDataSource(ABC):
    """Port interface for remote data sources (MSSQL, API, etc.)"""

    @abstractmethod
    async def fetch_latest_status(self, equipment_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch latest status for all/specified devices."""
        pass

    @abstractmethod
    async def fetch_device_status(self, equip_code: str, days: int = 30) -> List[Dict[str, Any]]:
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
    async def dispose(self) -> None:
        """Clean up resources."""
        pass


__all__ = ["IRemoteDataSource"]
