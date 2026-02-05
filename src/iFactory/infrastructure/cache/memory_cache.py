# src/iFactory/infrastructure/cache/memory_cache.py
"""
Infrastructure Adapter: In-Memory Cache with LRU eviction.

Features:
- LRU eviction when max size reached
- TTL-based expiration
- Tag-based invalidation
- Statistics tracking
- Async-safe operations
- Get-or-set pattern
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    TypeVar,
)

from iFactory.application.ports.cache import ICacheProvider, CacheStatistics

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with value, expiry, and metadata."""

    value: T
    expiry: float
    tags: Set[str] = field(default_factory=set)
    created_at: float = field(default_factory=time.time)
    access_count: int = 0
    last_accessed: float = field(default_factory=time.time)

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return time.time() > self.expiry

    @property
    def age_seconds(self) -> float:
        """Get age of entry in seconds."""
        return time.time() - self.created_at

    def touch(self) -> None:
        """Record an access."""
        self.access_count += 1
        self.last_accessed = time.time()


class MemoryCache(ICacheProvider):
    """
    In-Memory Cache with LRU eviction and TTL expiration.
    """

    __slots__ = (
        "_store",
        "_tags",
        "_lock",
        "_pending_gets",
        "_max_size",
        "_default_ttl",
        "_cleanup_interval",
        "_last_cleanup",
        "_stats",
    )

    def __init__(
        self,
        max_size: int = 1000,
        default_ttl: int = 300,
        cleanup_interval: int = 60,
    ) -> None:
        """
        Initialize MemoryCache.

        Args:
            max_size: Maximum number of entries
            default_ttl: Default TTL in seconds
            cleanup_interval: How often to cleanup expired entries (seconds)
        """
        # Use OrderedDict for LRU tracking
        self._store: OrderedDict[str, CacheEntry] = OrderedDict()
        self._tags: Dict[str, Set[str]] = {}  # tag -> set of keys
        self._lock = asyncio.Lock()
        self._pending_gets: Dict[str, asyncio.Future] = {}  # For deduplication
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._cleanup_interval = cleanup_interval
        self._last_cleanup = time.time()

        # Statistics
        self._stats = CacheStatistics(max_size=max_size)

        logger.debug(
            "MemoryCache initialized: max_size=%d, default_ttl=%ds",
            max_size,
            default_ttl,
        )

    # ========================================================================
    # Core Operations
    # ========================================================================

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
                await self._remove_entry(key)
                self._stats.expirations += 1
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            entry.touch()

            self._stats.hits += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: int = 0,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """
        Set value in cache with TTL and optional tags.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds (0 = use default)
            tags: Optional tags for group invalidation
        """
        ttl = ttl if ttl > 0 else self._default_ttl
        expiry = time.time() + ttl
        entry_tags = tags or set()

        async with self._lock:
            # Remove old entry if exists
            if key in self._store:
                await self._remove_entry(key)

            # Evict if necessary
            while len(self._store) >= self._max_size:
                await self._evict_lru()

            # Add new entry
            self._store[key] = CacheEntry(
                value=value,
                expiry=expiry,
                tags=entry_tags,
            )

            # Register tags
            for tag in entry_tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(key)

            self._update_size_stat()

    async def delete(self, key: str) -> bool:
        """Delete a key from cache. Returns True if key existed."""
        async with self._lock:
            if key in self._store:
                await self._remove_entry(key)
                return True
            return False

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        async with self._lock:
            if key not in self._store:
                return False

            entry = self._store[key]
            if entry.is_expired:
                await self._remove_entry(key)
                self._stats.expirations += 1
                return False

            return True

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            count = len(self._store)
            self._store.clear()
            self._tags.clear()
            self._stats.current_size = 0
            logger.debug("Cache cleared: %d entries removed", count)

    # ========================================================================
    # Bulk Operations
    # ========================================================================

    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values at once."""
        result = {}
        async with self._lock:
            await self._maybe_cleanup()

            for key in keys:
                if key not in self._store:
                    self._stats.misses += 1
                    continue

                entry = self._store[key]
                if entry.is_expired:
                    await self._remove_entry(key)
                    self._stats.expirations += 1
                    self._stats.misses += 1
                    continue

                self._store.move_to_end(key)
                entry.touch()
                self._stats.hits += 1
                result[key] = entry.value

        return result

    async def set_many(
        self,
        items: Dict[str, Any],
        ttl: int = 0,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """Set multiple values at once."""
        for key, value in items.items():
            await self.set(key, value, ttl, tags)

    async def delete_many(self, keys: List[str]) -> int:
        """Delete multiple keys. Returns count of deleted keys."""
        deleted = 0
        async with self._lock:
            for key in keys:
                if key in self._store:
                    await self._remove_entry(key)
                    deleted += 1
        return deleted

    # ========================================================================
    # Tag Operations
    # ========================================================================

    async def delete_by_tag(self, tag: str) -> int:
        """Delete all entries with given tag."""
        async with self._lock:
            keys = self._tags.pop(tag, set())
            deleted = 0

            for key in keys:
                if key in self._store:
                    await self._remove_entry(key, update_tags=False)
                    deleted += 1

            if deleted > 0:
                logger.debug("Deleted %d entries with tag '%s'", deleted, tag)

            return deleted

    async def get_keys_by_tag(self, tag: str) -> List[str]:
        """Get all keys with given tag."""
        async with self._lock:
            return list(self._tags.get(tag, set()))

    # ========================================================================
    # Advanced Operations
    # ========================================================================

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int = 0,
        tags: Optional[Set[str]] = None,
    ) -> T:
        """
        Get value or compute and cache it.

        Thread-safe: Only one factory call if multiple concurrent requests.
        """
        # Check cache first
        value = await self.get(key)
        if value is not None:
            return value

        # Check for pending computation
        async with self._lock:
            if key in self._pending_gets:
                # Wait for existing computation
                future = self._pending_gets[key]
            else:
                # Start new computation
                future = asyncio.get_event_loop().create_future()
                self._pending_gets[key] = future

        # If we didn't create the future, wait for it
        if key in self._pending_gets and self._pending_gets[key] is not future:
            return await future

        # Compute value
        try:
            computed_value = await factory()
            await self.set(key, computed_value, ttl, tags)
            future.set_result(computed_value)
            return computed_value
        except Exception as e:
            future.set_exception(e)
            raise
        finally:
            async with self._lock:
                self._pending_gets.pop(key, None)

    async def refresh(self, key: str, ttl: int) -> bool:
        """Refresh TTL for existing key."""
        async with self._lock:
            if key not in self._store:
                return False

            entry = self._store[key]
            if entry.is_expired:
                await self._remove_entry(key)
                return False

            entry.expiry = time.time() + ttl
            return True

    async def increment(
        self,
        key: str,
        delta: int = 1,
        default: int = 0,
    ) -> int:
        """Increment numeric value."""
        async with self._lock:
            if key in self._store:
                entry = self._store[key]
                if not entry.is_expired:
                    if isinstance(entry.value, (int, float)):
                        entry.value += delta
                        return int(entry.value)

            # Key doesn't exist or expired - create with default
            new_value = default + delta
            await self.set(key, new_value)
            return new_value

    # ========================================================================
    # Statistics
    # ========================================================================

    def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        self._stats.current_size = len(self._store)
        return self._stats

    def reset_stats(self) -> None:
        """Reset statistics."""
        self._stats = CacheStatistics(max_size=self._max_size)
        self._stats.current_size = len(self._store)

    # ========================================================================
    # Internal Helpers
    # ========================================================================

    async def _remove_entry(self, key: str, update_tags: bool = True) -> None:
        """Remove entry and update tag mappings."""
        if key not in self._store:
            return

        entry = self._store.pop(key)

        if update_tags:
            for tag in entry.tags:
                if tag in self._tags:
                    self._tags[tag].discard(key)
                    if not self._tags[tag]:
                        del self._tags[tag]

        self._update_size_stat()

    async def _evict_lru(self) -> None:
        """Evict least recently used entry."""
        if self._store:
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
            await self._remove_entry(key)
            self._stats.expirations += 1

        if expired_keys:
            logger.debug("Cleaned up %d expired entries", len(expired_keys))

    def _update_size_stat(self) -> None:
        """Update current size statistic."""
        self._stats.current_size = len(self._store)

    async def get_entry_with_metadata(self, key: str) -> Optional[CacheEntry]:
        """
        Get cache entry with full metadata.

        Used by SWR service to check entry age and determine
        if data is fresh, stale, or expired.

        Returns:
            CacheEntry with value, expiry, age_seconds, etc.
            None if key doesn't exist or is expired.

        Example:
            entry = await cache.get_entry_with_metadata("device:ABC")
            if entry:
                print(f"Age: {entry.age_seconds}s")
                print(f"Value: {entry.value}")
        """
        async with self._lock:
            await self._maybe_cleanup()

            if key not in self._store:
                self._stats.misses += 1
                return None

            entry = self._store[key]

            if entry.is_expired:
                await self._remove_entry(key)
                self._stats.expirations += 1
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._store.move_to_end(key)
            entry.touch()

            self._stats.hits += 1
            return entry

    async def get_with_age(self, key: str) -> Tuple[Optional[Any], float]:
        """
        Get value and its age in seconds.

        Returns:
            Tuple of (value, age_seconds)
            (None, 0) if not found

        Example:
            value, age = await cache.get_with_age("device:ABC")
            if value and age < 5:
                print("Fresh data!")
        """
        entry = await self.get_entry_with_metadata(key)

        if entry is None:
            return (None, 0.0)

        return (entry.value, entry.age_seconds)

    async def set_with_stale_ttl(
        self,
        key: str,
        value: Any,
        fresh_ttl: int,
        stale_ttl: int,
        tags: Optional[Set[str]] = None,
    ) -> None:
        """
        Set value with separate fresh and stale TTLs.

        The entry expires at stale_ttl, but is_fresh() returns False
        after fresh_ttl.

        Args:
            key: Cache key
            value: Value to cache
            fresh_ttl: Time in seconds data is fresh
            stale_ttl: Time in seconds data is usable (stale)
            tags: Optional tags for group invalidation

        Note: Uses stale_ttl for actual expiry, fresh_ttl for metadata.
        """
        expiry = time.time() + stale_ttl
        entry_tags = tags or set()

        async with self._lock:
            # Remove old entry if exists
            if key in self._store:
                await self._remove_entry(key)

            # Evict if necessary
            while len(self._store) >= self._max_size:
                await self._evict_lru()

            # Create entry with fresh_ttl as metadata
            entry = CacheEntry(
                value=value,
                expiry=expiry,
                tags=entry_tags,
            )
            # Store fresh_ttl for SWR checks
            entry._fresh_ttl = fresh_ttl

            self._store[key] = entry

            # Register tags
            for tag in entry_tags:
                if tag not in self._tags:
                    self._tags[tag] = set()
                self._tags[tag].add(key)

            self._update_size_stat()

    async def is_fresh(self, key: str, fresh_ttl: Optional[int] = None) -> bool:
        """
        Check if cached data is still fresh.

        Args:
            key: Cache key
            fresh_ttl: Fresh TTL in seconds (uses default if None)

        Returns:
            True if data exists and is fresh
        """
        entry = await self.get_entry_with_metadata(key)

        if entry is None:
            return False

        # Use stored fresh_ttl if available
        if fresh_ttl is None:
            fresh_ttl = getattr(entry, "_fresh_ttl", self._default_ttl)

        return entry.age_seconds < fresh_ttl

    async def get_keys_by_pattern(self, pattern: str) -> List[str]:
        """
        Get all keys matching a pattern.

        Supports simple prefix matching with '*'.

        Args:
            pattern: Pattern like "device:*" or "gantt:ABC*"

        Returns:
            List of matching keys
        """
        async with self._lock:
            if "*" not in pattern:
                # Exact match
                return [pattern] if pattern in self._store else []

            # Prefix match
            prefix = pattern.rstrip("*")
            return [key for key in self._store.keys() if key.startswith(prefix)]

    async def delete_by_pattern(self, pattern: str) -> int:
        """
        Delete all entries matching a pattern.

        Args:
            pattern: Pattern like "device:*"

        Returns:
            Number of entries deleted
        """
        keys = await self.get_keys_by_pattern(pattern)
        return await self.delete_many(keys)


# ============================================================================
# Typed Cache Wrapper
# ============================================================================


class TypedCache(Generic[T]):
    """
    Type-safe cache wrapper.

    Usage:
        device_cache: TypedCache[Device] = TypedCache(cache, "device:")
        await device_cache.set("ABC123", device)
        device = await device_cache.get("ABC123")  # Returns Optional[Device]
    """

    __slots__ = ("_cache", "_prefix", "_default_ttl")

    def __init__(
        self,
        cache: ICacheProvider,
        prefix: str = "",
        default_ttl: int = 60,
    ) -> None:
        self._cache = cache
        self._prefix = prefix
        self._default_ttl = default_ttl

    def _key(self, key: str) -> str:
        return f"{self._prefix}{key}"

    async def get(self, key: str) -> Optional[T]:
        return await self._cache.get(self._key(key))

    async def set(
        self,
        key: str,
        value: T,
        ttl: Optional[int] = None,
        tags: Optional[Set[str]] = None,
    ) -> None:
        await self._cache.set(
            self._key(key),
            value,
            ttl or self._default_ttl,
            tags,
        )

    async def delete(self, key: str) -> bool:
        return await self._cache.delete(self._key(key))

    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: Optional[int] = None,
    ) -> T:
        return await self._cache.get_or_set(
            self._key(key),
            factory,
            ttl or self._default_ttl,
        )


__all__ = [
    "MemoryCache",
    "CacheEntry",
    "TypedCache",
]
