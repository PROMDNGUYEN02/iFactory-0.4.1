# src/iFactory/domain/value_objects/material_batch.py
"""
Material Batch Value Object.

Represents a uniquely identifiable batch of raw materials.
"""

from __future__ import annotations

import re
from typing import Any, Final, Optional, Tuple

from ..common.value_object import ValueObject
from ..exceptions.domain_exceptions import InvalidMaterialError


class MaterialBatch(ValueObject):
    """
    Value object representing a uniquely identifiable batch of raw materials.

    A material batch is an immutable identifier for a group of materials
    that share the same origin, production date, or quality characteristics.

    Format Examples:
    - LOT-2024-001
    - BATCH20240115-A
    - MAT-001-2024

    Usage:
        batch = MaterialBatch.create("LOT-2024-001")
        print(batch.value)  # "LOT-2024-001"

        # Safe creation
        batch = MaterialBatch.try_create("invalid")  # Returns None
    """

    __slots__ = ("_value", "_prefix", "_date_part", "_sequence")

    MAX_LENGTH: Final[int] = 100
    MIN_LENGTH: Final[int] = 1
    _PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9\-_.]+$")
    _LOT_PATTERN: Final[re.Pattern[str]] = re.compile(r"^([A-Z]+)[-_]?(\d{4,8})?[-_]?(.*)$")

    def __init__(self, value: str) -> None:
        """
        Create MaterialBatch with validation.

        Args:
            value: Batch identifier string

        Raises:
            InvalidMaterialError: If value is empty or invalid
        """
        cleaned = self._validate(value)
        object.__setattr__(self, "_value", cleaned)

        # Parse components
        match = self._LOT_PATTERN.match(cleaned)
        if match:
            object.__setattr__(self, "_prefix", match.group(1) or "")
            object.__setattr__(self, "_date_part", match.group(2) or "")
            object.__setattr__(self, "_sequence", match.group(3) or "")
        else:
            object.__setattr__(self, "_prefix", "")
            object.__setattr__(self, "_date_part", "")
            object.__setattr__(self, "_sequence", cleaned)

    @classmethod
    def _validate(cls, value: str) -> str:
        """Validate and normalize batch identifier."""
        if not value:
            raise InvalidMaterialError.empty_lot_number()

        cleaned = str(value).strip().upper()

        if not cleaned:
            raise InvalidMaterialError.empty_lot_number()

        if len(cleaned) > cls.MAX_LENGTH:
            raise InvalidMaterialError(
                f"Batch identifier exceeds maximum length of {cls.MAX_LENGTH}",
                {"value": cleaned[:50] + "...", "max_length": cls.MAX_LENGTH},
            )

        if not cls._PATTERN.match(cleaned):
            raise InvalidMaterialError(
                f"Invalid batch identifier format: '{cleaned}'",
                {"value": cleaned},
            )

        return cleaned

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def create(cls, value: str) -> "MaterialBatch":
        """Factory method to create MaterialBatch."""
        return cls(value)

    @classmethod
    def try_create(cls, value: str) -> Optional["MaterialBatch"]:
        """
        Try to create MaterialBatch without raising exceptions.

        Returns None if validation fails.
        """
        try:
            return cls(value)
        except InvalidMaterialError:
            return None

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if value is a valid batch identifier."""
        try:
            cls._validate(value)
            return True
        except InvalidMaterialError:
            return False

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def value(self) -> str:
        """The batch identifier."""
        return self._value

    @property
    def prefix(self) -> str:
        """Batch prefix (e.g., 'LOT', 'BATCH')."""
        return self._prefix

    @property
    def date_part(self) -> str:
        """Date portion if present."""
        return self._date_part

    @property
    def sequence(self) -> str:
        """Sequence/suffix portion."""
        return self._sequence

    # ========================================================================
    # Equality
    # ========================================================================

    def _get_equality_components(self) -> Tuple[Any, ...]:
        """Return components for equality comparison."""
        return (self._value,)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MaterialBatch):
            return self._value == other._value
        if isinstance(other, str):
            try:
                return self._value == MaterialBatch._validate(other)
            except InvalidMaterialError:
                return False
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"MaterialBatch({self._value!r})"


__all__ = ["MaterialBatch"]
