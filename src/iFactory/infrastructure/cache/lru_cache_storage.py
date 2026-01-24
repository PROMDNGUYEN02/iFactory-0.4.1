"""
LRU Cache implementation with TTL support.

Changes:
- Made `size` a synchronous property (no I/O, no lock needed for read)
- Unified pattern matching strategy
- Added explicit pattern filtering delegation note
"""

from __future__ import annotations
import asyncio
import logging
from collections import OrderedDict
from datetime import timedelta
from typing import Callable, Generic, Optional, TypeVar, Awaitable
from .cache_storage import CacheStorage

__all__ = ["LRUCacheStorage"]
logger = logging.getLogger(__name__)
T = TypeVar("T")


class LRUCacheStorage(Generic[T]):
    """
    Thread-safe LRU cache with TTL support.

    Design Decisions:
        - `size` is a sync property (OrderedDict.__len__ is O(1), no I/O)
        - Pattern matching delegated to provider layer
        - Lock only held during mutations, not reads of size
    """

    __slots__ = ("_cache", "_max_size", "_ttl", "_lock", "_hits", "_misses")

    def __init__(self, max_size: int = 500, ttl_seconds: float = 30.0):
        self._cache: OrderedDict[str, CacheStorage[T]] = OrderedDict()
        self._max_size = max_size
        self._ttl: float = ttl_seconds
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    # ─────────────────────────────────────────────────────────────────
    # PROPERTIES (sync, no lock needed for atomic reads)
    # ─────────────────────────────────────────────────────────────────

    @property
    def size(self) -> int:
        """Current number of items (O(1), no lock needed)."""
        return len(self._cache)

    @property
    def max_size(self) -> int:
        """Maximum number of entries."""
        return self._max_size

    @property
    def hit_rate(self) -> float:
        """Cache hit rate (0.0 to 1.0)."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    # ─────────────────────────────────────────────────────────────────
    # CORE OPERATIONS
    # ─────────────────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[T]:
        """Get item if valid, update LRU ordering."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None
            self._cache.move_to_end(key)
            self._hits += 1
            return entry.data

    async def set(self, key: str, value: T, ttl: Optional[timedelta] = None) -> None:
        """Set item with optional TTL override."""
        async with self._lock:
            # Evict LRU if at capacity
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            ttl_seconds = ttl.total_seconds() if ttl else self._ttl
            self._cache[key] = CacheStorage(data=value, ttl_seconds=ttl_seconds)
            self._cache.move_to_end(key)

    async def delete(self, key: str) -> bool:
        """Delete item. Returns True if item existed."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return False
            if entry.is_expired:
                del self._cache[key]
                return False
            return True

    async def clear(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self._cache.clear()

    # ─────────────────────────────────────────────────────────────────
    # BULK OPERATIONS
    # ─────────────────────────────────────────────────────────────────

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: Optional[timedelta] = None,
    ) -> T:
        """Get value or create via factory if missing."""
        # Check cache first (separate lock acquisition)
        value = await self.get(key)
        if value is not None:
            return value

        # Factory call outside lock to prevent deadlocks
        value = await factory()
        await self.set(key, value, ttl)
        return value

    async def get_many(self, keys: list[str]) -> dict[str, Optional[T]]:
        """Get multiple values atomically."""
        result: dict[str, Optional[T]] = {}
        async with self._lock:
            for key in keys:
                entry = self._cache.get(key)
                if entry is None or entry.is_expired:
                    if entry and entry.is_expired:
                        del self._cache[key]
                    result[key] = None
                    self._misses += 1
                else:
                    self._cache.move_to_end(key)
                    result[key] = entry.data
                    self._hits += 1
        return result

    async def set_many(
        self, items: dict[str, T], ttl: Optional[timedelta] = None
    ) -> None:
        """Set multiple values atomically."""
        ttl_seconds = ttl.total_seconds() if ttl else self._ttl
        async with self._lock:
            for key, value in items.items():
                while len(self._cache) >= self._max_size:
                    self._cache.popitem(last=False)
                self._cache[key] = CacheStorage(data=value, ttl_seconds=ttl_seconds)
                self._cache.move_to_end(key)

    async def delete_many(self, keys: list[str]) -> int:
        """Delete multiple values. Returns count deleted."""
        async with self._lock:
            count = 0
            for key in keys:
                if key in self._cache:
                    del self._cache[key]
                    count += 1
            return count

    # ─────────────────────────────────────────────────────────────────
    # INTROSPECTION (pattern filtering delegated to Provider)
    # ─────────────────────────────────────────────────────────────────

    async def keys(self) -> list[str]:
        """
        Get all cached keys.

        Note: Pattern filtering is handled by Provider layer to support
        different matching strategies without coupling storage to patterns.
        """
        async with self._lock:
            return list(self._cache.keys())

    async def get_ttl(self, key: str) -> Optional[timedelta]:
        """Get remaining TTL for key."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired:
                return None
            return timedelta(seconds=entry.remaining_ttl)

    async def refresh_ttl(self, key: str, ttl: Optional[timedelta] = None) -> bool:
        """Refresh TTL for key. Returns False if key not found."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None or entry.is_expired:
                if entry:
                    del self._cache[key]
                return False
            entry.refresh()
            if ttl:
                entry.ttl_seconds = ttl.total_seconds()
            self._cache.move_to_end(key)
            return True

    # ─────────────────────────────────────────────────────────────────
    # MAINTENANCE
    # ─────────────────────────────────────────────────────────────────

    async def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        async with self._lock:
            expired = [k for k, v in self._cache.items() if v.is_expired]
            for key in expired:
                del self._cache[key]
            return len(expired)

    def get_stats(self) -> dict:
        """Get cache statistics (sync, read-only)."""
        return {
            "size": self.size,
            "max_size": self._max_size,
            "ttl_seconds": self._ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self.hit_rate,
        }

    def reset_stats(self) -> None:
        """Reset hit/miss counters."""
        self._hits = 0
        self._misses = 0
