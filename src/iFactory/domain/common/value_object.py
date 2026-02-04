# src/iFactory/domain/common/value_object.py
"""
Base Value Object classes with immutability and validation.

Value Objects are domain objects that:
- Have no identity (equality based on attributes)
- Are immutable
- Are self-validating
- Are interchangeable when equal
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Generic, Tuple, Type, TypeVar

T = TypeVar("T", bound="ValueObject")
V = TypeVar("V")


class ValueObject(ABC):
    """
    Base class for all domain value objects.

    Value Objects:
    - Are immutable (state cannot change after creation)
    - Have no identity - equality is based on all attributes
    - Are interchangeable when equal
    - Should be self-validating (validate in __init__)

    Design Principles:
    - All validation happens at construction time
    - Use __slots__ for memory efficiency
    - Override _get_equality_components() for proper equality

    Usage:
        class Money(ValueObject):
            __slots__ = ("_amount", "_currency")

            def __init__(self, amount: Decimal, currency: str) -> None:
                if amount < 0:
                    raise ValueError("Amount cannot be negative")
                if not currency:
                    raise ValueError("Currency is required")
                self._amount = amount
                self._currency = currency.upper()

            @property
            def amount(self) -> Decimal:
                return self._amount

            @property
            def currency(self) -> str:
                return self._currency

            def _get_equality_components(self) -> Tuple[Any, ...]:
                return (self._amount, self._currency)

            def add(self, other: Money) -> Money:
                if self._currency != other._currency:
                    raise ValueError("Cannot add different currencies")
                return Money(self._amount + other._amount, self._currency)
    """

    __slots__ = ()

    @abstractmethod
    def _get_equality_components(self) -> Tuple[Any, ...]:
        """
        Return tuple of components for equality comparison.

        All significant attributes should be included.
        Order matters for comparison.
        """
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

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Prevent attribute modification after initialization.

        Note: This works with __slots__ to ensure immutability.
        Use object.__setattr__ in __init__ to set initial values.
        """
        # Check if object is being initialized
        if not hasattr(self, "_initialized"):
            object.__setattr__(self, name, value)
            return

        raise AttributeError(f"Cannot modify {self.__class__.__name__}: Value objects are immutable")

    def _validate(self) -> None:
        """
        Override to add custom validation logic.

        Called automatically after __init__ if _mark_initialized() is used.

        Raises:
            ValueError: If validation fails
        """
        pass

    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize to dictionary.

        Override in subclasses for custom serialization.
        """
        result: Dict[str, Any] = {}
        for slot in self.__slots__:
            attr_name = slot.lstrip("_")
            if hasattr(self, slot):
                value = getattr(self, slot)
                if isinstance(value, ValueObject):
                    result[attr_name] = value.to_dict()
                else:
                    result[attr_name] = value
        return result


class SingleValueObject(ValueObject, Generic[V]):
    """
    Base for value objects wrapping a single value.

    Provides simpler interface for common case of single-value wrappers.

    Usage:
        class Email(SingleValueObject[str]):
            def __init__(self, value: str) -> None:
                if "@" not in value:
                    raise ValueError("Invalid email format")
                super().__init__(value.lower().strip())

        email = Email("User@Example.com")
        print(email.value)  # "user@example.com"
        print(str(email))   # "user@example.com"
    """

    __slots__ = ("_value",)

    def __init__(self, value: V) -> None:
        """
        Initialize with a single value.

        Override in subclasses to add validation.
        """
        object.__setattr__(self, "_value", value)

    @property
    def value(self) -> V:
        """The wrapped value."""
        return self._value

    def _get_equality_components(self) -> Tuple[Any, ...]:
        return (self._value,)

    def __str__(self) -> str:
        return str(self._value)

    def to_primitive(self) -> V:
        """Return the primitive value (alias for value property)."""
        return self._value


class CompositeValueObject(ValueObject):
    """
    Base for value objects with multiple components.

    Provides automatic equality based on all slots.

    Usage:
        class Address(CompositeValueObject):
            __slots__ = ("_street", "_city", "_postal_code")

            def __init__(self, street: str, city: str, postal_code: str):
                object.__setattr__(self, "_street", street)
                object.__setattr__(self, "_city", city)
                object.__setattr__(self, "_postal_code", postal_code)

            @property
            def street(self) -> str:
                return self._street
            # ... other properties
    """

    __slots__ = ()

    def _get_equality_components(self) -> Tuple[Any, ...]:
        """Automatically use all slots for equality."""
        components = []
        for cls in type(self).__mro__:
            if hasattr(cls, "__slots__"):
                for slot in cls.__slots__:
                    if slot and hasattr(self, slot):
                        components.append(getattr(self, slot))
        return tuple(components)


__all__ = [
    "ValueObject",
    "SingleValueObject",
    "CompositeValueObject",
]
