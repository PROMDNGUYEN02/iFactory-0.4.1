from __future__ import annotations
from dataclasses import dataclass
from ..exceptions.base import DomainError


@dataclass(frozen=True, slots=True)
class MaterialBatch:
    """Value object representing a uniquely identifiable batch of raw materials."""

    value: str

    def __post_init__(self):
        raw_val = str(self.value).strip()
        if not raw_val:
            raise DomainError("Material batch identifier cannot be empty.")
        object.__setattr__(self, "value", raw_val)

    def __str__(self) -> str:
        return self.value
