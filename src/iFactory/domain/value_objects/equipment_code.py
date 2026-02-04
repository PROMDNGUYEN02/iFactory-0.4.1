# src/iFactory/domain/value_objects/equipment_code.py
"""
Equipment Code Value Object.
"""

from __future__ import annotations

import re
from typing import Final, Tuple, Any

from ..exceptions.domain_exceptions import InvalidEquipmentCodeError


class EquipmentCode:
    """
    Identity Value Object for Factory Equipment.
    """

    __slots__ = ("_value",)

    MAX_LENGTH: Final[int] = 50
    MIN_LENGTH: Final[int] = 1
    _PATTERN: Final[re.Pattern] = re.compile(r"^[A-Za-z0-9\-_]+$")

    def __init__(self, value: str) -> None:
        self._value = self._validate(value)

    @classmethod
    def create(cls, value: str) -> EquipmentCode:
        """Factory method to create EquipmentCode."""
        return cls(value)

    @classmethod
    def _validate(cls, value: str) -> str:
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
        """Check if a string is a valid equipment code."""
        try:
            cls._validate(value)
            return True
        except InvalidEquipmentCodeError:
            return False

    @property
    def value(self) -> str:
        return self._value

    def _get_equality_components(self) -> Tuple[Any, ...]:
        return (self._value,)

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"EquipmentCode({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, EquipmentCode):
            return self._value == other._value
        if isinstance(other, str):
            return self._value == other.strip().upper()
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)

    def __lt__(self, other: EquipmentCode) -> bool:
        if not isinstance(other, EquipmentCode):
            return NotImplemented
        return self._value < other._value


__all__ = ["EquipmentCode"]
