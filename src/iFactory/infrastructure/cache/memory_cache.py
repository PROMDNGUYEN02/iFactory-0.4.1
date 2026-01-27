"""
In-memory caching implementation.
"""

from collections import OrderedDict
from typing import Any, Optional, TypeVar, Generic

K = TypeVar("K")
V = TypeVar("V")


class AsyncLRUCache(Generic[K, V]):
    """
    Simple Least Recently Used (LRU) cache.
    Thread-safe enough for asyncio usage where operations are atomic.
    """

    def __init__(self, capacity: int = 1000):
        self._capacity = capacity
        self._cache: OrderedDict[K, V] = OrderedDict()

    async def get(self, key: K) -> Optional[V]:
        if key not in self._cache:
            return None
        self._cache.move_to_end(key)
        return self._cache[key]

    async def put(self, key: K, value: V) -> None:
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = value
        if len(self._cache) > self._capacity:
            self._cache.popitem(last=False)

    async def clear(self) -> None:
        self._cache.clear()

    async def remove(self, key: K) -> None:
        if key in self._cache:
            del self._cache[key]
