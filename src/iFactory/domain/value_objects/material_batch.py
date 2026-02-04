# src/iFactory/domain/value_objects/material_batch.py
"""
Material Batch Value Object.

Represents a uniquely identifiable batch of raw materials.
"""

from __future__ import annotations

from ..common.value_object import ValueObject
from ..exceptions.base import DomainError


class MaterialBatch(ValueObject):
    """
    Value object representing a uniquely identifiable batch of raw materials.

    A material batch is an immutable identifier for a group of materials
    that share the same origin, production date, or quality characteristics.

    Usage:
        batch = MaterialBatch("LOT-2024-001")
        print(batch.value)  # "LOT-2024-001"
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        """
        Create MaterialBatch with validation.

        Args:
            value: Batch identifier string

        Raises:
            DomainError: If value is empty
        """
        cleaned = str(value).strip() if value else ""
        if not cleaned:
            raise DomainError("Material batch identifier cannot be empty.")
        self._value = cleaned

    @classmethod
    def create(cls, value: str) -> "MaterialBatch":
        """Factory method to create MaterialBatch."""
        return cls(value)

    @property
    def value(self) -> str:
        """The batch identifier."""
        return self._value

    def _get_equality_components(self) -> tuple:
        """Return components for equality comparison."""
        return (self._value,)

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"MaterialBatch({self._value!r})"


__all__ = ["MaterialBatch"]
