"""
In-memory cache provider implementing Application's CacheProvider interface.

This adapter translates between the Application interface (using timedelta)
and the infrastructure LRUCacheStorage implementation.
"""

from __future__ import annotations
import fnmatch
from datetime import timedelta
from typing import Awaitable, Callable, Generic, Optional, TypeVar, Union

from iFactory.application.interfaces import CacheProvider
from .lru_cache_storage import LRUCacheStorage

__all__ = ["InMemoryCacheProvider"]
T = TypeVar("T")


class InMemoryCacheProvider(CacheProvider[T], Generic[T]):
    """
    In-memory implementation of CacheProvider.

    This is an ADAPTER that:
    - Implements the Application layer's CacheProvider interface
    - Delegates to infrastructure's LRUCacheStorage
    - Handles pattern matching for keys()

    Thread Safety:
        All operations are async-safe via LRUCacheStorage's internal locking.
    """

    __slots__ = ("_cache", "_default_ttl")

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: Union[timedelta, float] = timedelta(seconds=30),
    ):
        """
        Initialize provider.

        Args:
            max_size: Maximum number of cached entries
            default_ttl: Default time-to-live for entries (seconds as float/int or timedelta)
        """
        self._default_ttl = default_ttl

        # Handle timedelta, int, or float inputs for default_ttl
        if isinstance(default_ttl, timedelta):
            ttl_seconds = default_ttl.total_seconds()
        elif isinstance(default_ttl, (int, float)):
            ttl_seconds = float(default_ttl)
        else:
            raise TypeError(f"Invalid type for default_ttl: {type(default_ttl)}. " "Expected timedelta, int, or float.")

        self._cache: LRUCacheStorage[T] = LRUCacheStorage(
            max_size=max_size,
            ttl_seconds=ttl_seconds,
        )

    # ─────────────────────────────────────────────────────────────────
    # CacheProvider Interface Implementation
    # ─────────────────────────────────────────────────────────────────

    async def get(self, key: str) -> Optional[T]:
        """Get value from cache."""
        return await self._cache.get(key)

    async def set(self, key: str, value: T, ttl: Optional[timedelta] = None) -> None:
        """Set value in cache with optional TTL."""
        await self._cache.set(key, value, ttl)

    async def delete(self, key: str) -> bool:
        """Delete value from cache."""
        return await self._cache.delete(key)

    async def exists(self, key: str) -> bool:
        """Check if key exists and is valid."""
        return await self._cache.exists(key)

    async def clear(self) -> None:
        """Clear all cached values."""
        await self._cache.clear()

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: Optional[timedelta] = None,
    ) -> T:
        """Get value or create and cache it."""
        return await self._cache.get_or_set(key, factory, ttl)

    async def get_many(self, keys: list[str]) -> dict[str, Optional[T]]:
        """Get multiple values."""
        return await self._cache.get_many(keys)

    async def set_many(self, items: dict[str, T], ttl: Optional[timedelta] = None) -> None:
        """Set multiple values."""
        await self._cache.set_many(items, ttl)

    async def delete_many(self, keys: list[str]) -> int:
        """Delete multiple values."""
        return await self._cache.delete_many(keys)

    async def size(self) -> int:
        """Get number of cached items."""
        return await self._cache.size

    async def keys(self, pattern: Optional[str] = None) -> list[str]:
        """
        Get keys matching optional glob pattern.

        Pattern matching uses fnmatch (glob-style):
            - "*" matches everything
            - "device:*" matches all device keys
            - "device:???:status" matches device:ABC:status
        """
        all_keys = await self._cache.keys()
        if pattern is None:
            return all_keys
        return [k for k in all_keys if fnmatch.fnmatch(k, pattern)]

    async def get_ttl(self, key: str) -> Optional[timedelta]:
        """Get remaining TTL for key."""
        return await self._cache.get_ttl(key)

    async def refresh_ttl(self, key: str, ttl: Optional[timedelta] = None) -> bool:
        """Refresh TTL for key."""
        return await self._cache.refresh_ttl(key, ttl)

    # ─────────────────────────────────────────────────────────────────
    # Infrastructure-specific extensions (not in interface)
    # ─────────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get cache statistics for monitoring."""
        return self._cache.get_stats()

    async def cleanup_expired(self) -> int:
        """Manual cleanup of expired entries."""
        return await self._cache.cleanup_expired()
