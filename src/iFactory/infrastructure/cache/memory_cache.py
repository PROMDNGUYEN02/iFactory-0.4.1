# File: infrastructure/cache/memory_cache.py
"""
Infrastructure Adapter: In-Memory Cache with LRU eviction.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Dict, Generic, Optional, TypeVar

from iFactory.application.ports.cache import ICacheProvider

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value and expiry."""

    value: T
    expiry: float
    created_at: float = field(default_factory=time.time)
    access_count: int = 0

    @property
    def is_expired(self) -> bool:
        return time.time() > self.expiry

    def touch(self) -> None:
        """Record an access."""
        self.access_count += 1


@dataclass
class CacheStats:
    """Cache statistics for monitoring."""

    hits: int = 0
    misses: int = 0
    evictions: int = 0
    expirations: int = 0
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
            "expirations": self.expirations,
            "current_size": self.current_size,
            "max_size": self.max_size,
        }


class MemoryCache(ICacheProvider):
    """
    In-Memory Cache with LRU eviction and TTL expiration.

    Features:
    - Max size limit with LRU eviction
    - TTL-based expiration
    - Async-safe with lock
    - Statistics tracking
    - Periodic cleanup of expired entries

    Usage:
        cache = MemoryCache(max_size=1000, default_ttl=300)
        await cache.set("key", value, ttl=60)
        value = await cache.get("key")
    """

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,  # 5 minutes
        cleanup_interval: int = 60,  # Cleanup every 60 seconds
    ) -> None:
        # Use OrderedDict for LRU tracking
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

        # Statistics
        self._stats = CacheStats(max_size=max_size)

        logger.debug("MemoryCache initialized: max_size=%d, default_ttl=%ds", max_size, default_ttl)

    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Returns None if key doesn't exist or is expired.
        Updates LRU order on access.
        """
        async with self._lock:
            await self._maybe_cleanup()

            if key not in self._store:
                self._stats.misses += 1
                return None

            entry = self._store[key]

            if entry.is_expired:
                del self._store[key]
                self._stats.expirations += 1
                self._stats.misses += 1
                self._update_size_stat()
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            entry.touch()

            self._stats.hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache with TTL.

        Evicts LRU entries if cache is full.
        """
        ttl = ttl if ttl is not None else self._default_ttl
        expiry = time.time() + ttl

        async with self._lock:
            # If key exists, update it
            if key in self._store:
                self._store[key] = CacheEntry(value=value, expiry=expiry)
                self._store.move_to_end(key)
                return

            # Evict if necessary
            while len(self._store) >= self._max_size:
                await self._evict_lru()

            # Add new entry
            self._store[key] = CacheEntry(value=value, expiry=expiry)
            self._update_size_stat()

    async def delete(self, key: str) -> bool:
        """Delete a key from cache. Returns True if key existed."""
        async with self._lock:
            if key in self._store:
                del self._store[key]
                self._update_size_stat()
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        async with self._lock:
            if key not in self._store:
                return False

            entry = self._store[key]
            if entry.is_expired:
                del self._store[key]
                self._stats.expirations += 1
                self._update_size_stat()
                return False

            return True

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            self._stats.current_size = 0
            logger.debug("Cache cleared: %d entries removed", count)

    async def get_or_set(
        self,
        key: str,
        factory: callable,
        ttl: Optional[int] = None,
    ) -> Any:
        """
        Get value or compute and cache it.

        Useful pattern for cache-aside:
            value = await cache.get_or_set(
                "expensive_key",
                lambda: compute_expensive_value(),
                ttl=300
            )
        """
        value = await self.get(key)
        if value is not None:
            return value

        # Compute value
        if asyncio.iscoroutinefunction(factory):
            value = await factory()
        else:
            value = factory()

        await self.set(key, value, ttl)
        return value

    def get_stats(self) -> CacheStats:
        """Get cache statistics."""
        return self._stats

    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._store:
            # popitem(last=False) removes the first (oldest) item
            key, _ = self._store.popitem(last=False)
            self._stats.evictions += 1
            self._update_size_stat()
            logger.debug("Evicted LRU entry: %s", key)

    async def _maybe_cleanup(self) -> None:
        """Periodically cleanup expired entries."""
        now = time.time()
        if now - self._last_cleanup < self._cleanup_interval:
            return

        self._last_cleanup = now
        await self._cleanup_expired()

    async def _cleanup_expired(self) -> None:
        """Remove all expired entries."""
        now = time.time()
        expired_keys = [key for key, entry in self._store.items() if entry.expiry < now]

        for key in expired_keys:
            del self._store[key]
            self._stats.expirations += 1

        if expired_keys:
            self._update_size_stat()
            logger.debug("Cleaned up %d expired entries", len(expired_keys))

    def _update_size_stat(self) -> None:
        """Update current size statistic."""
        self._stats.current_size = len(self._store)


# Typed cache for specific use cases
class TypedCache(Generic[T]):
    """
    Type-safe cache wrapper.

    Usage:
        device_cache: TypedCache[Device] = TypedCache(cache, "device:")
        await device_cache.set("ABC123", device)
        device = await device_cache.get("ABC123")  # Returns Optional[Device]
    """

    def __init__(self, cache: ICacheProvider, prefix: str = "") -> None:
        self._cache = cache
        self._prefix = prefix

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Optional[T]:
        return await self._cache.get(self._key(key))

    async def set(self, key: str, value: T, ttl: int = 60) -> None:
        await self._cache.set(self._key(key), value, ttl)

    async def delete(self, key: str) -> bool:
        return await self._cache.delete(self._key(key))


__all__ = ["MemoryCache", "CacheEntry", "CacheStats", "TypedCache"]
