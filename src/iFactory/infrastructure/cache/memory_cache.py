"""
Infrastructure: In-Memory Cache.
Thread-safe Async LRU implementation with TTL.
"""

from __future__ import annotations
import asyncio
from collections import OrderedDict
from datetime import timedelta, datetime
from typing import Generic, Optional, TypeVar, Union, Any
from dataclasses import dataclass

from iFactory.application.ports.cache import ICacheProvider

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    data: T
    expires_at: datetime

    @property
    def is_expired(self) -> bool:
        return datetime.now() >= self.expires_at


class MemoryCache(ICacheProvider, Generic[T]):
    """
    Async LRU cache implementation.
    """

    def __init__(self, max_size: int = 500, default_ttl_seconds: float = 30.0):
        self._cache: OrderedDict[str, CacheEntry[T]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = timedelta(seconds=default_ttl_seconds)
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                return None
            if entry.is_expired:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return entry.data

    async def set(self, key: str, value: Any, ttl: Union[int, float] = 60) -> None:
        async with self._lock:
            while len(self._cache) >= self._max_size:
                self._cache.popitem(last=False)

            effective_ttl = timedelta(seconds=ttl)
            expiration = datetime.now() + effective_ttl

            self._cache[key] = CacheEntry(data=value, expires_at=expiration)
            self._cache.move_to_end(key)

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def exists(self, key: str) -> bool:
        async with self._lock:
            entry = self._cache.get(key)
            return entry is not None and not entry.is_expired
