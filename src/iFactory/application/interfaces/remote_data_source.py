from abc import ABC, abstractmethod
from typing import Dict, Any


class IRemoteDataSource(ABC):
    @abstractmethod
    async def fetch_device_status(self, equip_code: str) -> Dict[str, Any]:
        pass
