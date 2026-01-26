from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional


class IRemoteDataSource(ABC):
    @abstractmethod
    async def fetch_latest_status(self, equipment_codes: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    async def fetch_device_status(self, equip_code: str) -> Optional[Dict[str, Any]]:
        pass
