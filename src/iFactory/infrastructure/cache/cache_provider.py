"""
Standard In-Memory Cache Provider implementation.
"""

import asyncio
from typing import Any, Optional
from collections import OrderedDict


class InMemoryCacheProvider:
    """
    Simple, thread-safe LRU Cache implementation for the Application Use Cases.
    Supports TTL (Time-To-Live) signatures used by the Application layer.
    """

    def __init__(self, max_size: int = 500):
        self._cache = OrderedDict()
        self._max_size = max_size
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Retrieve an item from the cache."""
        async with self._lock:
            if key not in self._cache:
                return None
            self._cache.move_to_end(key)
            return self._cache[key]

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Store an item in the cache.
        Accepts 'ttl' (in seconds) to satisfy the ICacheProvider interface.
        """
        async with self._lock:
            self._cache[key] = value
            self._cache.move_to_end(key)
            if len(self._cache) > self._max_size:
                self._cache.popitem(last=False)

    def clear(self) -> None:
        """Clear all cached items."""
        self._cache.clear()
