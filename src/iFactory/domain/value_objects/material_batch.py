from __future__ import annotations

from ..exceptions.base import DomainError


class MaterialBatch:
    """
    Value object representing a uniquely identifiable batch of raw materials.
    """

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        cleaned = str(value).strip() if value else ""
        if not cleaned:
            raise DomainError("Material batch identifier cannot be empty.")
        self._value = cleaned

    @property
    def value(self) -> str:
        return self._value

    def __str__(self) -> str:
        return self._value

    def __repr__(self) -> str:
        return f"MaterialBatch({self._value!r})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, MaterialBatch):
            return self._value == other._value
        return NotImplemented

    def __hash__(self) -> int:
        return hash(self._value)
