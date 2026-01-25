"""
Infrastructure Cache Adapter.
"""

from typing import Any, Optional
from iFactory.application.interfaces.cache_provider import ICacheProvider


class InMemoryCacheProvider(ICacheProvider):
    def __init__(self, max_size: int = 1000):
        self._cache = {}
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if len(self._cache) >= self._max_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[key] = value

    async def delete(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
