import asyncio
import time
from typing import Any, Dict, Optional, Tuple

from iFactory.application.ports.cache import ICacheProvider


class MemoryCache(ICacheProvider):
    """
    Infrastructure Adapter: In-Memory Cache.
    Implements ICacheProvider port.
    """

    def __init__(self, max_size: int = 1000) -> None:
        self._store: Dict[str, Tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def get(self, key: str) -> Optional[Any]:
        async with self._lock:
            if key not in self._store:
                return None

            value, expiry = self._store[key]
            if time.time() > expiry:
                del self._store[key]
                return None

            return value

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        expiry = time.time() + ttl
        async with self._lock:
            # Basic eviction if full
            if len(self._store) >= self._max_size:
                self._prune_expired()
                # If still full after pruning, evict the oldest inserted (FIFO-like behavior of dict)
                if len(self._store) >= self._max_size:
                    self._store.pop(next(iter(self._store)), None)

            self._store[key] = (value, expiry)

    def _prune_expired(self) -> None:
        """Helper to remove expired items."""
        now = time.time()
        # Create list to avoid runtime error during iteration
        keys_to_remove = [k for k, v in self._store.items() if v[1] < now]
        for k in keys_to_remove:
            del self._store[k]

    async def clear(self) -> None:
        async with self._lock:
            self._store.clear()
