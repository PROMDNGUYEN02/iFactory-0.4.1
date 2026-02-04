# src/iFactory/application/ports/cache.py
"""
Enhanced Cache Port with advanced features.

Provides interface for caching with:
- Type-safe operations
- Statistics tracking
- Bulk operations
- Tags for group invalidation
- Distributed cache support
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
)

T = TypeVar("T")


@dataclass
class CacheStatistics:
    """Cache statistics for monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
    current_size: int = 0
    max_size: int = 0

    # Timing
    total_get_time_ms: float = 0.0
    total_set_time_ms: float = 0.0

    @property
    def hit_rate(self) -> float:
        """Calculate hit rate (0.0 to 1.0)."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    @property
    def avg_get_time_ms(self) -> float:
        """Average get operation time."""
        total = self.hits + self.misses
        return self.total_get_time_ms / total if total > 0 else 0.0

    def record_hit(self, time_ms: float = 0.0) -> None:
        """Record a cache hit."""
        self.hits += 1
        self.total_get_time_ms += time_ms

    def record_miss(self, time_ms: float = 0.0) -> None:
        """Record a cache miss."""
        self.misses += 1
        self.total_get_time_ms += time_ms

    def record_eviction(self) -> None:
        """Record an eviction."""
        self.evictions += 1

    def reset(self) -> None:
        """Reset all statistics."""
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0
        self.total_get_time_ms = 0.0
        self.total_set_time_ms = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": f"{self.hit_rate:.2%}",
            "evictions": self.evictions,
            "expirations": self.expirations,
            "current_size": self.current_size,
            "max_size": self.max_size,
            "avg_get_time_ms": f"{self.avg_get_time_ms:.2f}",
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

    Usage:
        # Basic operations
        await cache.set("user:123", user_data, ttl=300)
        user = await cache.get("user:123")

        # Get-or-set (cache-aside pattern)
        user = await cache.get_or_set(
            "user:123",
            lambda: fetch_user_from_db(123),
            ttl=300
        )

        # Bulk operations
        users = await cache.get_many(["user:1", "user:2", "user:3"])

        # Tag-based invalidation
        await cache.set("user:123", user, tags={"users", "active"})
        await cache.delete_by_tag("users")  # Deletes all user entries
    """

    # ========================================================================
    # Core Operations
    # ========================================================================

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value by key.

        Returns None if not found or expired.
        """
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
            value: Value to cache (must be serializable)
            ttl: Time to live in seconds
            tags: Optional tags for group invalidation
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete key.

        Returns True if key existed and was deleted.
        """
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
    # Bulk Operations
    # ========================================================================

    @abstractmethod
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """
        Get multiple values at once.

        Returns dict mapping keys to values.
        Missing keys are omitted from result.
        """
        pass

    @abstractmethod
    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: int = 60,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Set multiple values at once."""
        pass

    @abstractmethod
    async def delete_many(self, keys: List[str]) -> int:
        """
        Delete multiple keys.

        Returns count of actually deleted keys.
        """
        pass

    # ========================================================================
    # Tag Operations
    # ========================================================================

    @abstractmethod
    async def delete_by_tag(self, tag: str) -> int:
        """
        Delete all entries with given tag.

        Returns count of deleted entries.
        """
        pass

    @abstractmethod
    async def get_keys_by_tag(self, tag: str) -> List[str]:
        """Get all keys with given tag."""
        pass

    # ========================================================================
    # Advanced Operations
    # ========================================================================

    @abstractmethod
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int = 60,
        tags: Optional[Set[str]] = None,
    ) -> T:
        """
        Get value or compute and cache it.

        Thread-safe: Only one factory call if multiple concurrent requests.

        Args:
            key: Cache key
            factory: Async function to compute value if not cached
            ttl: Time to live in seconds
            tags: Optional tags for the cached value

        Returns:
            Cached or computed value
        """
        pass

    @abstractmethod
    async def refresh(self, key: str, ttl: int) -> bool:
        """
        Refresh TTL for existing key.

        Returns True if key exists and was refreshed.
        """
        pass

    @abstractmethod
    async def increment(
        self,
        key: str,
        delta: int = 1,
        default: int = 0,
    ) -> int:
        """
        Increment numeric value.

        Creates key with default value if not exists.
        Returns new value.
        """
        pass

    # ========================================================================
    # Statistics
    # ========================================================================

    @abstractmethod
    def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        pass

    def reset_stats(self) -> None:
        """Reset statistics (optional, default no-op)."""
        pass


class IDistributedCache(ICacheProvider):
    """
    Extended interface for distributed caching.

    Adds features needed for multi-instance deployments:
    - Distributed locks
    - Pub/Sub for cache invalidation
    """

    @abstractmethod
    async def acquire_lock(
        self,
        key: str,
        timeout: float = 10.0,
        retry_interval: float = 0.1,
    ) -> bool:
        """
        Acquire a distributed lock.

        Args:
            key: Lock key
            timeout: Lock timeout in seconds
            retry_interval: Time between retry attempts

        Returns:
            True if lock acquired
        """
        pass

    @abstractmethod
    async def release_lock(self, key: str) -> bool:
        """
        Release a distributed lock.

        Returns True if lock was held and released.
        """
        pass

    @abstractmethod
    async def extend_lock(self, key: str, timeout: float) -> bool:
        """
        Extend lock timeout.

        Returns True if lock was held and extended.
        """
        pass

    @abstractmethod
    async def publish(self, channel: str, message: Any) -> int:
        """
        Publish message to channel.

        Returns number of subscribers that received the message.
        """
        pass

    @abstractmethod
    async def subscribe(
        self,
        channel: str,
        callback: Callable[[Any], Awaitable[None]],
    ) -> None:
        """Subscribe to channel with callback."""
        pass

    @abstractmethod
    async def unsubscribe(self, channel: str) -> None:
        """Unsubscribe from channel."""
        pass


__all__ = [
    "ICacheProvider",
    "IDistributedCache",
    "CacheStatistics",
]
