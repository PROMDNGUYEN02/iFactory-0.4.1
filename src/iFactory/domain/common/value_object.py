# src/iFactory/domain/common/value_object.py
"""
Base Value Object class with value-based equality.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Tuple, TypeVar

T = TypeVar("T", bound="ValueObject")


class ValueObject(ABC):
    """
    Base class for all domain value objects.

    Value Objects:
    - Are immutable
    - Have no identity - equality is based on attributes
    - Are interchangeable when equal
    - Should be self-validating
    """

    __slots__ = ()

    @abstractmethod
    def _get_equality_components(self) -> Tuple[Any, ...]:
        """Return tuple of components for equality comparison."""
        raise NotImplementedError

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, self.__class__):
            return False
        return self._get_equality_components() == other._get_equality_components()

    def __ne__(self, other: object) -> bool:
        return not self.__eq__(other)

    def __hash__(self) -> int:
        return hash(self._get_equality_components())

    def __repr__(self) -> str:
        components = self._get_equality_components()
        if len(components) == 1:
            return f"{self.__class__.__name__}({components[0]!r})"
        return f"{self.__class__.__name__}{components!r}"


class SingleValueObject(ValueObject):
    """Base for value objects wrapping a single value."""

    __slots__ = ("_value",)

    def __init__(self, value: Any) -> None:
        object.__setattr__(self, "_value", value)

    @property
    def value(self) -> Any:
        return self._value

    def _get_equality_components(self) -> Tuple[Any, ...]:
        return (self._value,)

    def __str__(self) -> str:
        return str(self._value)


__all__ = ["ValueObject", "SingleValueObject"]
