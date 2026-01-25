from __future__ import annotations
import re
from dataclasses import dataclass
from ..exceptions import InvalidEquipmentCodeError


@dataclass(frozen=True, slots=True)
class EquipmentCode:
    value: str
    _PATTERN = re.compile(r"^[A-Z]{2,4}[0-9]*$")

    def __post_init__(self):
        raw_val = str(self.value).strip().upper()
        if not raw_val:
            raise InvalidEquipmentCodeError.empty()
        if not self._PATTERN.match(raw_val):
            raise InvalidEquipmentCodeError.invalid_format(raw_val)
        object.__setattr__(self, "value", raw_val)

    def __str__(self) -> str:
        return self.value
