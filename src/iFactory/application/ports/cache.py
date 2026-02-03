# File: application/ports/cache.py
"""
Application Port: Cache Provider.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional


class ICacheProvider(ABC):
    """
    Port interface for caching.

    Implementations may use in-memory, Redis, Memcached, etc.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if not found or expired."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Set value with TTL in seconds."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """Delete key. Returns True if key existed."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass


__all__ = ["ICacheProvider"]
