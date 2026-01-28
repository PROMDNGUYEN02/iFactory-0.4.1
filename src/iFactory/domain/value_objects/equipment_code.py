from __future__ import annotations

import re
from typing import Final

from ..exceptions.domain_exceptions import InvalidEquipmentCodeError


class EquipmentCode:
    """
    Identity Value Object for Factory Equipment.
    Enforces naming conventions and provides immutable identity.
    """

    __slots__ = ("_value",)

    # Domain Rules for Code format
    MAX_LENGTH: Final[int] = 50
    MIN_LENGTH: Final[int] = 1
    _PATTERN: Final[re.Pattern] = re.compile(r"^[A-Za-z0-9\-_]+$")

    def __init__(self, value: str) -> None:
        self._value = self._validate(value)

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

    @property
    def value(self) -> str:
        return self._value

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
