"""
Cache Provider Interface (Port).
Thuộc Tầng Application - Không chứa logic cụ thể.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ICacheProvider(ABC):
    """Abstract Port for Caching mechanisms in Clean Architecture."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Store a value in the cache with a Time-To-Live (TTL)."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Remove a value from the cache."""
        pass
