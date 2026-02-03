# src/application/ports/cache.py - ENHANCED
"""
Enhanced Cache Port with advanced features.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Set, TypeVar

T = TypeVar("T")


@dataclass
class CacheStatistics:
    """Cache statistics for monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    current_size: int = 0
    max_size: int = 0

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "evictions": self.evictions,
            "current_size": self.current_size,
            "max_size": self.max_size,
        }


class ICacheProvider(ABC):
    """
    Enhanced cache provider interface.

    Features:
    - Type-safe operations
    - Statistics tracking
    - Bulk operations
    - Tags for invalidation
    - Get-or-set pattern
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key. Returns None if not found or expired."""
        pass

    @abstractmethod
    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 60,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """
        Set value with TTL and optional tags.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            tags: Optional tags for group invalidation
        """
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

    # ========================================================================
    # Advanced Operations
    # ========================================================================

    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values at once.

        Returns dict mapping keys to values (missing keys are omitted).
        """
        pass

    @abstractmethod
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: int = 60,
    ) -> None:
        """Set multiple values at once."""
        pass

    @abstractmethod
    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys. Returns count of deleted keys."""
        pass

    @abstractmethod
    async def delete_by_tag(self, tag: str) -> int:
        """
        Delete all entries with given tag.

        Returns count of deleted entries.
        """
        pass

    @abstractmethod
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int = 60,
    ) -> T:
        """
        Get value or compute and cache it.

        Thread-safe: Only one factory call if multiple concurrent requests.
        """
        pass

    @abstractmethod
    def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        pass


class IDistributedCache(ICacheProvider):
    """
    Extended interface for distributed caching.

    Adds features needed for multi-instance deployments.
    """

    @abstractmethod
    async def acquire_lock(
        self,
        key: str,
        timeout: float = 10.0,
    ) -> bool:
        """
        Acquire a distributed lock.

        Args:
            key: Lock key
            timeout: Lock timeout in seconds

        Returns:
            True if lock acquired
        """
        pass

    @abstractmethod
    async def release_lock(self, key: str) -> None:
        """Release a distributed lock."""
        pass

    @abstractmethod
    async def publish(self, channel: str, message: Any) -> None:
        """Publish message to channel."""
        pass

    @abstractmethod
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Subscribe to channel."""
        pass


__all__ = [
    "ICacheProvider",
    "IDistributedCache",
    "CacheStatistics",
]
