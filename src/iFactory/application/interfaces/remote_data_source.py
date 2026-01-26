from abc import ABC, abstractmethod
from typing import Dict, Any, List


class IRemoteDataSource(ABC):
    @abstractmethod
    async def fetch_device_status(self, equip_code: str) -> Dict[str, Any]:
        """Fetch status for a single device."""
        pass

    @abstractmethod
    async def fetch_all_devices(self) -> List[Dict[str, Any]]:
        """Fetch latest status for ALL devices."""
        pass
