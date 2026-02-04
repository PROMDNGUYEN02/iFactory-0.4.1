# src/iFactory/domain/common/entity.py
"""
Base Entity class with identity-based equality.

Entities are domain objects that have a distinct identity that runs through
time and different representations. Their equality is based on identity,
not attributes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar

# Type variable for entity ID - can be str, int, UUID, or composite
TId = TypeVar("TId")


class Entity(ABC, Generic[TId]):
    """
    Base class for all domain entities.

    Entities have:
    - A unique identity that persists through state changes
    - Equality based on identity, not attributes
    - A lifecycle (can be created, modified, deleted)

    Design Principles:
    - Identity is immutable once assigned
    - Two entities are equal if they have the same identity
    - Entities can change state while maintaining identity

    Usage:
        class User(Entity[UserId]):
            def __init__(self, user_id: UserId, name: str):
                self._id = user_id
                self._name = name

            @property
            def id(self) -> UserId:
                return self._id

            @property
            def name(self) -> str:
                return self._name

            def rename(self, new_name: str) -> None:
                self._name = new_name

    Note:
        For aggregates (entities that are consistency boundaries),
        use AggregateRoot instead.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def id(self) -> TId:
        """
        The unique identifier for this entity.

        This property must be implemented by all subclasses.
        The ID should be immutable once assigned.
        """
        raise NotImplementedError

    @property
    def is_transient(self) -> bool:
        """
        Check if entity has not been persisted yet.

        Override this in subclasses if using auto-generated IDs.
        """
        return self.id is None

    def same_identity_as(self, other: Entity[TId]) -> bool:
        """
        Check if this entity has the same identity as another.

        This is an explicit alternative to __eq__ for clarity.
        """
        if other is None:
            return False
        if not isinstance(other, Entity):
            return False
        return self.id == other.id

    def __eq__(self, other: object) -> bool:
        """
        Entities are equal if they have the same type and identity.
        """
        if other is None:
            return False
        if not isinstance(other, self.__class__):
            return False
        # Handle transient entities
        if self.is_transient or other.is_transient:
            return self is other
        return self.id == other.id

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        """
        Hash based on class name and identity.

        Note: Transient entities should not be added to sets/dicts.
        """
        if self.is_transient:
            return id(self)
        return hash((self.__class__.__name__, self.id))

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(id={self.id!r})"

    def __str__(self) -> str:
        return f"{self.__class__.__name__}[{self.id}]"


class EntityId(ABC):
    """
    Base class for strongly-typed entity IDs.

    Usage:
        @dataclass(frozen=True)
        class UserId(EntityId):
            value: str

            def __str__(self) -> str:
                return self.value
    """

    __slots__ = ()

    @abstractmethod
    def __str__(self) -> str:
        """String representation of the ID."""
        raise NotImplementedError

    @abstractmethod
    def __hash__(self) -> int:
        """IDs must be hashable."""
        raise NotImplementedError

    @abstractmethod
    def __eq__(self, other: Any) -> bool:
        """IDs must be comparable."""
        raise NotImplementedError


__all__ = ["Entity", "EntityId", "TId"]
