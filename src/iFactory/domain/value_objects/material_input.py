from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .equipment_code import EquipmentCode
from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class MaterialInput:
    equipment_code: EquipmentCode
    material_batch: str
    feeding_time: datetime

    def __post_init__(self):
        if not self.material_batch or not self.material_batch.strip():
            raise ValidationError.required_field("material_batch")

    @classmethod
    def create(cls, code: str, batch: str, time: datetime) -> MaterialInput:
        return cls(equipment_code=EquipmentCode(code), material_batch=batch, feeding_time=time)
