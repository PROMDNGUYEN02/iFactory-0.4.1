from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..exceptions import ValidationError
from .equipment_code import EquipmentCode


@dataclass(frozen=True, slots=True)
class MaterialInput:
    equipment_code: EquipmentCode
    material_batch: str
    feeding_time: datetime

    def __post_init__(self):
        if not self.material_batch.strip():
            raise ValidationError.required_field("material_batch")

    @classmethod
    def create(cls, equip_code: str, material_batch: str, feeding_time: datetime) -> "MaterialInput":
        return cls(
            equipment_code=EquipmentCode(equip_code),
            material_batch=material_batch,
            feeding_time=feeding_time,
        )
