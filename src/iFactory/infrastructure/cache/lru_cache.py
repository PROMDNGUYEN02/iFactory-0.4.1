"""
LRU Cache implementation with TTL support.
Pure infrastructure component using asyncio locks for thread safety.
"""

from __future__ import annotations
import asyncio
from collections import OrderedDict
from datetime import timedelta, datetime
from typing import Callable, Generic, Optional, TypeVar, Awaitable, Union
from dataclasses import dataclass

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    data: T
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at


class LRUCacheStorage(Generic[T]):
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size: int = 500, ttl_seconds: float = 30.0):
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = timedelta(seconds=ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[T]:
        """Retrieve an item from the cache."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry.data

    async def set(self, key: str, value: T, ttl: Optional[Union[timedelta, int, float]] = None) -> None:
        """
        Store an item in the cache.
        Supports TTL as a timedelta object or an integer/float (seconds).
        """
        async with self._lock:
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            # Convert int/float seconds to timedelta for compatibility with Use Cases
            if isinstance(ttl, (int, float)):
                effective_ttl = timedelta(seconds=ttl)
            else:
                effective_ttl = ttl or self._default_ttl

            expiration = datetime.now() + effective_ttl
            self._cache[key] = CacheEntry(data=value, expires_at=expiration)
            self._cache.move_to_end(key)

    async def clear(self) -> None:
        """Clear all entries."""
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        async with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired
