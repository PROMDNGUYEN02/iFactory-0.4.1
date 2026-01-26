from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime

from .equipment_code import EquipmentCode
from .material_batch import MaterialBatch


@dataclass(frozen=True, slots=True)
class MaterialInput:
    """Represents a feeding event of raw materials into a machine."""

    equipment_code: EquipmentCode
    material_batch: MaterialBatch
    feeding_time: datetime

    @classmethod
    def create(cls, code: str, batch: str, time: datetime) -> MaterialInput:
        return cls(equipment_code=EquipmentCode(code), material_batch=MaterialBatch(batch), feeding_time=time)
