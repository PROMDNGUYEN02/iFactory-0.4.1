"""
Application Port: Remote Data Source.
Interface for fetching data from external systems (PLCs, APIs, Legacy DBs).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union


class IRemoteDataSource(ABC):
    """
    Interface for external data fetching.
    Implementations (Adapters) reside in Infrastructure.
    """

    @abstractmethod
    async def fetch_latest_status(self, equipment_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Fetch status for multiple devices."""
        pass

    @abstractmethod
    async def fetch_device_status(self, equip_code: str, days: int = 30) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """Fetch status for a single device."""
        pass
