"""
Infrastructure Cache Adapter.
Triển khai ICacheProvider sử dụng bộ nhớ RAM (In-Memory).
"""

from typing import Any, Optional

# QUAN TRỌNG: Import trực tiếp từ file cụ thể, KHÔNG qua __init__ của interfaces
from iFactory.application.interfaces.cache_provider import ICacheProvider


class InMemoryCacheProvider(ICacheProvider):
    """Concrete implementation of ICacheProvider using Python dict."""

    def __init__(self):
        self._cache = {}

    async def get(self, key: str) -> Optional[Any]:
        return self._cache.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        # Ở môi trường thực tế, ttl sẽ được xử lý qua background task hoặc Redis
        self._cache[key] = value

    async def delete(self, key: str) -> None:
        if key in self._cache:
            del self._cache[key]
