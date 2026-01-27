from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IRemoteDataSource(ABC):
    """
    Port interface for external data sources (e.g., MSSQL, PLC, REST API).
    Returns raw data structures (dicts) to be mapped by Application commands.
    """

    @abstractmethod
    async def fetch_latest_status(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetches the latest status snapshot for devices.
        Returns: List of dicts with keys ['equip_code', 'raw_status', 'timestamp']
        """
        pass

    @abstractmethod
    async def fetch_device_status(self, equip_code: str) -> Optional[Dict[str, Any]]:
        """
        Fetches status for a single device.
        """
        pass
