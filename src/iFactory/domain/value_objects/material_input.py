from __future__ import annotations

from datetime import datetime

from .equipment_code import EquipmentCode
from .material_batch import MaterialBatch


class MaterialInput:
    """
    Represents a feeding event of raw materials into a machine.

    Immutable record of material consumption.
    """

    __slots__ = ("_equipment_code", "_material_batch", "_feeding_time")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        material_batch: MaterialBatch,
        feeding_time: datetime,
    ) -> None:
        self._equipment_code = equipment_code
        self._material_batch = material_batch
        self._feeding_time = feeding_time

    @classmethod
    def create(
        cls,
        code: str,
        batch: str,
        time: datetime,
    ) -> MaterialInput:
        return cls(
            equipment_code=EquipmentCode(code),
            material_batch=MaterialBatch(batch),
            feeding_time=time,
        )

    @property
    def equipment_code(self) -> EquipmentCode:
        return self._equipment_code

    @property
    def material_batch(self) -> MaterialBatch:
        return self._material_batch

    @property
    def feeding_time(self) -> datetime:
        return self._feeding_time

    @property
    def device_code(self) -> str:
        return self._equipment_code.value

    @property
    def batch_id(self) -> str:
        return self._material_batch.value

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, MaterialInput):
            return NotImplemented
        return (
            self._equipment_code == other._equipment_code
            and self._material_batch == other._material_batch
            and self._feeding_time == other._feeding_time
        )

    def __hash__(self) -> int:
        return hash(
            (
                self._equipment_code,
                self._material_batch,
                self._feeding_time,
            )
        )

    def __repr__(self) -> str:
        return f"MaterialInput(code={self.device_code!r}, " f"batch={self.batch_id!r}, " f"time={self._feeding_time!r})"
