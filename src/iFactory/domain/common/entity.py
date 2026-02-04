# src/iFactory/domain/common/entity.py
"""
Base Entity class with identity-based equality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

TId = TypeVar("TId")


class Entity(ABC, Generic[TId]):
    """
    Base class for all domain entities.

    Entities have:
    - A unique identity that persists through state changes
    - Equality based on identity, not attributes
    """

    __slots__ = ()

    @property
    @abstractmethod
    def id(self) -> TId:
        """The unique identifier for this entity."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, self.__class__):
            return False
        return self.id == other.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash((self.__class__.__name__, self.id))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r})"


__all__ = ["Entity", "TId"]
