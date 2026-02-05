# src/iFactory/application/services/swr_service.py
"""
Stale-While-Revalidate Service.

Implements SWR caching pattern for optimal UX:
- Serve stale data immediately
- Refresh in background
- Update cache transparently

Usage:
    swr = SWRService(cache_provider, policy)

    data, is_fresh = await swr.get_with_swr(
        "device:ABC123",
        factory=lambda: fetch_from_db("ABC123"),
    )

    if not is_fresh:
        # Data is stale, but usable
        # Background refresh already triggered
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Awaitable, Callable, Dict, Optional, Set, Tuple, TypeVar

from iFactory.application.ports.cache import ICacheProvider

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CachePolicy:
    """Policy for SWR caching behavior."""

    # TTL config
    fresh_ttl: int = 5  # Data fresh for 5 seconds
    stale_ttl: int = 300  # Data usable for 5 minutes

    # Refresh config
    background_refresh_threshold: float = 0.8  # Refresh at 80% of fresh_ttl
    enable_background_refresh: bool = True

    # Deduplication
    deduplicate_refreshes: bool = True


@dataclass
class CacheMetrics:
    """Metrics for SWR operations."""

    total_requests: int = 0
    cache_hits_fresh: int = 0
    cache_hits_stale: int = 0
    cache_misses: int = 0
    background_refreshes: int = 0
    failed_refreshes: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total_hits = self.cache_hits_fresh + self.cache_hits_stale
        if self.total_requests == 0:
            return 0.0
        return total_hits / self.total_requests

    @property
    def fresh_rate(self) -> float:
        """Calculate fresh hit rate."""
        if self.total_requests == 0:
            return 0.0
        return self.cache_hits_fresh / self.total_requests

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "cache_hits_fresh": self.cache_hits_fresh,
            "cache_hits_stale": self.cache_hits_stale,
            "cache_misses": self.cache_misses,
            "hit_rate": f"{self.hit_rate:.1%}",
            "fresh_rate": f"{self.fresh_rate:.1%}",
            "background_refreshes": self.background_refreshes,
            "failed_refreshes": self.failed_refreshes,
        }


class SWRService:
    """
    Stale-While-Revalidate Service.

    Provides optimal caching with background refresh:
    1. Check cache for data
    2. If fresh → return immediately
    3. If stale → return stale + trigger background refresh
    4. If miss → fetch + cache + return

    Features:
    - Configurable TTL for fresh/stale
    - Background refresh deduplication
    - Metrics tracking
    - Async-safe

    Thread Safety:
        All operations are async-safe via cache provider's locks.
    """

    def __init__(
        self,
        cache: ICacheProvider,
        policy: Optional[CachePolicy] = None,
    ):
        self._cache = cache
        self._policy = policy or CachePolicy()

        # Track in-flight refreshes to prevent duplicates
        self._refreshing_keys: Set[str] = set()
        self._refresh_lock = asyncio.Lock()

        # Metrics
        self._metrics = CacheMetrics()

        logger.info(
            "[SWRService] Initialized with fresh_ttl=%ds, stale_ttl=%ds",
            self._policy.fresh_ttl,
            self._policy.stale_ttl,
        )

    async def get_with_swr(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        fresh_ttl: Optional[int] = None,
        stale_ttl: Optional[int] = None,
    ) -> Tuple[Optional[T], bool]:
        """
        Get value with Stale-While-Revalidate pattern.

        Args:
            key: Cache key
            factory: Async function to fetch fresh data
            fresh_ttl: Override fresh TTL
            stale_ttl: Override stale TTL

        Returns:
            Tuple of (value, is_fresh)
            - (data, True): Fresh data from cache or factory
            - (data, False): Stale data from cache (refresh triggered)
            - (None, True): No data available (miss + factory failed)

        Examples:
            >>> data, is_fresh = await swr.get_with_swr(
            ...     "device:ABC",
            ...     lambda: fetch_device("ABC"),
            ... )
            >>> if is_fresh:
            ...     print("Fresh data!")
            ... else:
            ...     print("Stale data, refreshing in background...")
        """
        self._metrics.total_requests += 1

        fresh_ttl = fresh_ttl or self._policy.fresh_ttl
        stale_ttl = stale_ttl or self._policy.stale_ttl

        # Try to get from cache
        cached_value = await self._cache.get(key)

        if cached_value is not None:
            # Get entry metadata for age check
            entry = await self._get_cache_entry(key)

            if entry:
                age = entry.age_seconds

                # Case 1: Fresh data
                if age < fresh_ttl:
                    self._metrics.cache_hits_fresh += 1
                    logger.debug(f"[SWR] Fresh hit: {key} (age={age:.1f}s)")
                    return (cached_value, True)

                # Case 2: Stale but usable
                if age < stale_ttl:
                    self._metrics.cache_hits_stale += 1
                    logger.debug(f"[SWR] Stale hit: {key} (age={age:.1f}s)")

                    # Trigger background refresh if needed
                    refresh_threshold = fresh_ttl * self._policy.background_refresh_threshold

                    if age > refresh_threshold and self._policy.enable_background_refresh:
                        asyncio.create_task(self._background_refresh(key, factory, stale_ttl))

                    return (cached_value, False)  # Stale

        # Case 3: Cache miss - fetch synchronously
        self._metrics.cache_misses += 1
        logger.debug(f"[SWR] Cache miss: {key}")

        try:
            fresh_value = await factory()

            if fresh_value is not None:
                await self._cache.set(key, fresh_value, ttl=stale_ttl)
                logger.debug(f"[SWR] Fetched and cached: {key}")

            return (fresh_value, True)

        except Exception as e:
            logger.error(f"[SWR] Factory failed for {key}: {e}")
            return (None, True)

    async def _background_refresh(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: int,
    ) -> None:
        """
        Refresh cache in background without blocking.

        Features:
        - Deduplication of concurrent refreshes
        - Error handling
        - Metrics tracking
        """
        # Check if already refreshing
        if self._policy.deduplicate_refreshes:
            async with self._refresh_lock:
                if key in self._refreshing_keys:
                    logger.debug(f"[SWR] Refresh already in progress: {key}")
                    return
                self._refreshing_keys.add(key)

        try:
            self._metrics.background_refreshes += 1
            logger.debug(f"[SWR] Background refresh started: {key}")

            fresh_value = await factory()

            if fresh_value is not None:
                await self._cache.set(key, fresh_value, ttl=ttl)
                logger.debug(f"[SWR] Background refresh completed: {key}")
            else:
                logger.warning(f"[SWR] Background refresh returned None: {key}")

        except Exception as e:
            self._metrics.failed_refreshes += 1
            logger.warning(f"[SWR] Background refresh failed for {key}: {e}")

        finally:
            async with self._refresh_lock:
                self._refreshing_keys.discard(key)

    async def _get_cache_entry(self, key: str) -> Optional[Any]:
        """
        Get cache entry with metadata.

        Note: This assumes the cache provider has a method to get
        entry metadata. If not available, falls back to age estimation.
        """
        # Try to get entry with metadata
        if hasattr(self._cache, "get_entry_with_metadata"):
            return await self._cache.get_entry_with_metadata(key)

        # Fallback: Estimate age (conservative - assume stale)
        # This is a simplified fallback - ideally enhance cache to support metadata
        return None

    async def invalidate(self, key: str) -> bool:
        """
        Invalidate a cache entry.

        Returns:
            True if key existed and was deleted
        """
        return await self._cache.delete(key)

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching pattern.

        Returns:
            Number of keys invalidated
        """
        if hasattr(self._cache, "delete_by_pattern"):
            return await self._cache.delete_by_pattern(pattern)

        # Fallback: Not all caches support pattern deletion
        logger.warning("[SWR] Cache does not support pattern invalidation")
        return 0

    def get_metrics(self) -> Dict[str, Any]:
        """Get SWR metrics."""
        return self._metrics.to_dict()

    def reset_metrics(self) -> None:
        """Reset metrics."""
        self._metrics = CacheMetrics()


__all__ = [
    "SWRService",
    "CachePolicy",
    "CacheMetrics",
]
