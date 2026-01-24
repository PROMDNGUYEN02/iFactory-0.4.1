"""
Cache provider interface - Contract for caching abstraction.

This interface defines a simple caching contract that can be
implemented with various backends (in-memory, Redis, etc.).
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Awaitable, Callable, Generic, Optional, TypeVar
__all__ = ['CacheProvider']

T = TypeVar('T')


class CacheProvider(ABC, Generic[T]):
    """
    Abstract cache provider interface.
    Provides a simple key-value cache with TTL support.
    Implementations may use different backends.
    Type Parameters:
        T: Type of cached values.

    Design Notes:
        - All methods are async for consistency with remote caches.
        - TTL is specified per-item for flexibility.
        - Supports both simple get/set and get-or-create patterns.
    """

    @abstractmethod
    async def get(self, key: str) -> Optional[T]:
        """
        Retrieve a value from the cache by its key.

        Args:
            key: The unique identifier for the cached item.

        Returns:
            The cached value if found and not expired, otherwise None.
        """

    @abstractmethod
    async def set(
        self, key: str, value: T, ttl: Optional[timedelta] = None
    ) -> None:
        """
        Set a value in the cache.

        Args:
            key: The unique identifier for the item.
            value: The value to cache.
            ttl: Time-to-live for the item. If None, uses default backend TTL.
        """

    @abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete a value from the cache.

        Args:
            key: The unique identifier for the item.

        Returns:
            True if the key existed and was deleted, False otherwise.
        """

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """
        Check if a key exists in the cache.

        Args:
            key: The unique identifier for the item.

        Returns:
            True if the key exists and has not expired, False otherwise.
        """

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cached values from the store."""

    @abstractmethod
    async def get_or_set(
        self,
        key: str,
        factory: Callable[[], Awaitable[T]],
        ttl: Optional[timedelta] = None,
    ) -> T:
        """
        Get value from cache or create and cache it if missing.

        Implements the cache-aside pattern (concurrency-safe if
        implemented correctly).

        Args:
            key: The unique identifier for the item.
            factory: An async function that generates the value if not cached.
            ttl: Time-to-live for the newly created value.

        Returns:
            The cached or newly created value.
        """

    @abstractmethod
    async def get_many(self, keys: list[str]) -> dict[str, Optional[T]]:
        """
        Retrieve multiple values from the cache.

        Args:
            keys: A list of unique identifiers.

        Returns:
            A dictionary mapping keys to their corresponding cached values.
            Missing keys will have a value of None.
        """

    @abstractmethod
    async def set_many(
        self, items: dict[str, T], ttl: Optional[timedelta] = None
    ) -> None:
        """
        Set multiple values in the cache.

        Args:
            items: A dictionary of key-value pairs to cache.
            ttl: Time-to-live applied to all items. If None, uses default
                backend TTL.
        """

    @abstractmethod
    async def delete_many(self, keys: list[str]) -> int:
        """
        Delete multiple values from the cache.

        Args:
            keys: A list of unique identifiers.

        Returns:
            The number of items that were actually deleted.
        """

    @abstractmethod
    async def size(self) -> int:
        """
        Get the number of items currently in the cache.

        Returns:
            The count of cached items.
        """

    @abstractmethod
    async def keys(self, pattern: Optional[str] = None) -> list[str]:
        """
        Get cached keys, optionally filtered by a glob pattern.

        Args:
            pattern: An optional glob pattern (e.g., "user:*") to filter keys.

        Returns:
            A list of keys matching the criteria.
        """

    @abstractmethod
    async def get_ttl(self, key: str) -> Optional[timedelta]:
        """
        Get the remaining Time-To-Live for a specific key.

        Args:
            key: The unique identifier for the item.

        Returns:
            The remaining TTL, or None if the key doesn't exist.
        """

    @abstractmethod
    async def refresh_ttl(
        self, key: str, ttl: Optional[timedelta] = None
    ) -> bool:
        """
        Refresh the TTL for an existing key.

        Args:
            key: The unique identifier for the item.
            ttl: The new TTL. If None, uses the default backend TTL.

        Returns:
            True if the key existed and TTL was refreshed, False otherwise.
        """
