# src/iFactory/domain/value_objects/equipment_code.py
from __future__ import annotations
import re
from dataclasses import dataclass

from ..exceptions import InvalidEquipmentCodeError


@dataclass(frozen=True, slots=True)
class EquipmentCode:
    """
    Value Object: Đại diện cho mã thiết bị.
    - frozen=True: Đảm bảo bất biến (Immutable).
    - slots=True: Tối ưu bộ nhớ (quan trọng cho Desktop app).
    """

    value: str

    # Regex quy tắc nghiệp vụ: 2-4 chữ cái hoa + số (VD: CA1, ACT02)
    _PATTERN = re.compile(r"^[A-Z]{2,4}[0-9]*$")

    def __post_init__(self):
        """Validate ngay khi khởi tạo."""
        raw_val = str(self.value).strip().upper()

        if not raw_val:
            raise InvalidEquipmentCodeError.empty()

        if not self._PATTERN.match(raw_val):
            raise InvalidEquipmentCodeError.invalid_format(raw_val)

        # Ghi đè giá trị đã chuẩn hóa (uppercase) vào frozen field
        object.__setattr__(self, "value", raw_val)

    @classmethod
    def from_string(cls, raw_code: str) -> EquipmentCode:
        """Factory method rõ nghĩa."""
        return cls(raw_code)

    def __str__(self) -> str:
        return self.value
