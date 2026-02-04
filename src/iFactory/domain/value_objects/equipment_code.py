# src/iFactory/domain/value_objects/equipment_code.py
"""
Equipment Code Value Object.

Represents a unique identifier for manufacturing equipment.
"""

from __future__ import annotations

import re
from functools import total_ordering
from typing import Any, Final, Optional, Tuple

from ..common.value_object import ValueObject
from ..exceptions.domain_exceptions import InvalidEquipmentCodeError


@total_ordering
class EquipmentCode(ValueObject):
    """
    Identity Value Object for Factory Equipment.

    Format: [PREFIX]-[NUMBER] or [PREFIX][NUMBER]
    Examples: CNC-001, CNC001, ROBOT-A1, ASSEMBLY-01

    The prefix typically indicates the equipment type:
    - CNC: CNC Machine
    - CCL: Coating Line
    - ASM: Assembly Station
    - etc.

    Usage:
        code = EquipmentCode.create("CNC-001")
        print(code.value)      # "CNC-001"
        print(code.prefix)     # "CNC"
        print(code.number)     # "001"

        # Comparison
        if code1 == code2:
            print("Same equipment")

        # Sorting
        codes = sorted([code3, code1, code2])
    """

    __slots__ = ("_value", "_prefix", "_number")

    # Validation constants
    MAX_LENGTH: Final[int] = 50
    MIN_LENGTH: Final[int] = 1
    _PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9\-_]+$")
    _PREFIX_PATTERN: Final[re.Pattern[str]] = re.compile(r"^([A-Z]+)[-_]?(.*)$")

    def __init__(self, value: str) -> None:
        """
        Create EquipmentCode.

        Use factory method `create()` for better error messages.

        Args:
            value: Raw equipment code string

        Raises:
            InvalidEquipmentCodeError: If validation fails
        """
        validated = self._validate(value)
        object.__setattr__(self, "_value", validated)

        # Extract prefix and number
        match = self._PREFIX_PATTERN.match(validated)
        if match:
            object.__setattr__(self, "_prefix", match.group(1))
            object.__setattr__(self, "_number", match.group(2) or "")
        else:
            object.__setattr__(self, "_prefix", validated)
            object.__setattr__(self, "_number", "")

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def create(cls, value: str) -> "EquipmentCode":
        """
        Factory method to create EquipmentCode with validation.

        Preferred way to create instances.

        Args:
            value: Equipment code string

        Returns:
            Validated EquipmentCode

        Raises:
            InvalidEquipmentCodeError: If validation fails
        """
        return cls(value)

    @classmethod
    def try_create(cls, value: str) -> Optional["EquipmentCode"]:
        """
        Try to create EquipmentCode without raising exceptions.

        Args:
            value: Equipment code string

        Returns:
            EquipmentCode if valid, None otherwise
        """
        try:
            return cls(value)
        except InvalidEquipmentCodeError:
            return None

    # ========================================================================
    # Validation
    # ========================================================================

    @classmethod
    def _validate(cls, value: str) -> str:
        """
        Validate and normalize equipment code.

        Returns normalized (uppercase, trimmed) value.
        """
        if not value:
            raise InvalidEquipmentCodeError.empty()

        cleaned = str(value).strip().upper()

        if not cleaned:
            raise InvalidEquipmentCodeError.empty()

        if len(cleaned) > cls.MAX_LENGTH:
            raise InvalidEquipmentCodeError.too_long(cleaned, cls.MAX_LENGTH)

        if not cls._PATTERN.match(cleaned):
            raise InvalidEquipmentCodeError.invalid_format(cleaned)

        return cleaned

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """
        Check if a string is a valid equipment code without raising.

        Args:
            value: String to validate

        Returns:
            True if valid
        """
        try:
            cls._validate(value)
            return True
        except InvalidEquipmentCodeError:
            return False

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def value(self) -> str:
        """The normalized equipment code."""
        return self._value

    @property
    def prefix(self) -> str:
        """
        Equipment type prefix.

        Examples: "CNC", "CCL", "ASM"
        """
        return self._prefix

    @property
    def number(self) -> str:
        """
        Equipment number portion.

        Examples: "001", "A1", "01"
        """
        return self._number

    @property
    def equipment_type(self) -> str:
        """Alias for prefix - the equipment type."""
        return self._prefix

    def with_number(self, new_number: str) -> "EquipmentCode":
        """
        Create new code with different number but same prefix.

        Args:
            new_number: New number portion

        Returns:
            New EquipmentCode
        """
        separator = "-" if "-" in self._value else ""
        return EquipmentCode.create(f"{self._prefix}{separator}{new_number}")

    def matches_prefix(self, prefix: str) -> bool:
        """Check if code matches given prefix."""
        return self._prefix == prefix.upper()

    # ========================================================================
    # Equality
    # ========================================================================

    def _get_equality_components(self) -> Tuple[Any, ...]:
        return (self._value,)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EquipmentCode):
            return self._value == other._value
        if isinstance(other, str):
            try:
                return self._value == EquipmentCode._validate(other)
            except InvalidEquipmentCodeError:
                return False
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __lt__(self, other: "EquipmentCode") -> bool:
        """Enable sorting by prefix first, then number."""
        if not isinstance(other, EquipmentCode):
            return NotImplemented
        # Compare prefix first, then number
        if self._prefix != other._prefix:
            return self._prefix < other._prefix
        # Try numeric comparison for number portion
        try:
            return int(self._number) < int(other._number)
        except ValueError:
            return self._number < other._number

    # ========================================================================
    # String Representations
    # ========================================================================

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"EquipmentCode({self._value!r})"


__all__ = ["EquipmentCode"]
