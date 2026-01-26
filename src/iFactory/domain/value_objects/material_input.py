from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from .equipment_code import EquipmentCode
from ..exceptions import DomainError


@dataclass(frozen=True, slots=True)
class MaterialInput:
    """Represents a feeding event of raw materials into a machine."""

    equipment_code: EquipmentCode
    material_batch: str
    feeding_time: datetime

    def __post_init__(self):
        if not self.material_batch or not self.material_batch.strip():
            raise DomainError("Material batch identifier cannot be empty.")

    @classmethod
    def create(cls, code: str, batch: str, time: datetime) -> MaterialInput:
        return cls(equipment_code=EquipmentCode(code), material_batch=batch, feeding_time=time)
