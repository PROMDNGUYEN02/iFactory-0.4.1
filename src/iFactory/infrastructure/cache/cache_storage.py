"""
Cache entry - Generic cache container with TTL support.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from time import time
from typing import Generic, TypeVar

__all__ = ["CacheStorage"]
T = TypeVar("T")


@dataclass(slots=True)
class CacheStorage(Generic[T]):
    """
    Generic cache entry with TTL support.

    Attributes:
        data: Cached data
        ttl_seconds: Time-to-live in seconds
        created_at: Creation timestamp
    """

    data: T
    ttl_seconds: float = 30.0
    created_at: float = field(default_factory=time)

    @property
    def is_expired(self) -> bool:
        """Check if entry has expired."""
        return self.age_seconds > self.ttl_seconds

    @property
    def is_valid(self) -> bool:
        """Check if entry is still valid."""
        return not self.is_expired

    @property
    def age_seconds(self) -> float:
        """Get age in seconds since creation."""
        return time() - self.created_at

    @property
    def remaining_ttl(self) -> float:
        """Get remaining TTL in seconds (0 if expired)."""
        remaining = self.ttl_seconds - self.age_seconds
        return max(0.0, remaining)

    def refresh(self) -> None:
        """Refresh the entry (reset creation time)."""
        self.created_at = time()

    def extend_ttl(self, additional_seconds: float) -> None:
        """Extend TTL by specified seconds."""
        self.ttl_seconds += additional_seconds

    @classmethod
    def create(cls, data: T, ttl_seconds: float = 30.0) -> "CacheStorage[T]":
        """Create new cache entry."""
        return cls(data=data, ttl_seconds=ttl_seconds)
