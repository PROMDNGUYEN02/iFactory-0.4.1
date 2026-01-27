from abc import ABC, abstractmethod
from typing import Any, Optional


class ICacheProvider(ABC):
    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        pass
