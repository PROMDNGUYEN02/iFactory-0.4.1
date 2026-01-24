from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

__all__ = ["MaterialInput"]


@dataclass(frozen=True, slots=True)
class MaterialInput:
    """
    Entity: Thông tin nguyên liệu đầu vào.

    Đây là Entity đại diện cho một bản ghi lịch sử nguyên liệu.
    Sử dụng frozen=True để đảm bảo bất biến (Immutability).
    """

    equip_code: str
    material_batch: str
    feeding_time: datetime

    @classmethod
    def create(cls, equip_code: str, material_batch: str, feeding_time: datetime) -> "MaterialInput":
        """
        Factory method để tạo instance từ các giá trị thô.
        Giúp đóng gói logic tạo object.
        """
        return cls(
            equip_code=equip_code,
            material_batch=material_batch,
            feeding_time=feeding_time,
        )
