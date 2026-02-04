# src/iFactory/domain/value_objects/material_input.py
"""
Material Input Value Object.

Represents a feeding event of raw materials into a machine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from ..common.value_object import ValueObject
from .equipment_code import EquipmentCode
from .material_batch import MaterialBatch


class MaterialInput(ValueObject):
    """
    Represents a feeding event of raw materials into a machine.

    This is an immutable record of material consumption that can be
    used for traceability, inventory management, and quality control.

    Usage:
        input_record = MaterialInput(
            equipment_code=EquipmentCode.create("CNC-001"),
            material_batch=MaterialBatch("LOT-2024-001"),
            feeding_time=datetime.now()
        )
    """

    __slots__ = ("_equipment_code", "_material_batch", "_feeding_time")

    def __init__(
        self,
        equipment_code: EquipmentCode,
        material_batch: MaterialBatch,
        feeding_time: datetime,
    ) -> None:
        """
        Create MaterialInput record.

        Args:
            equipment_code: Device that received the material
            material_batch: Batch identifier
            feeding_time: When material was fed
        """
        self._equipment_code = equipment_code
        self._material_batch = material_batch
        self._feeding_time = feeding_time

    @classmethod
    def create(
        cls,
        equipment_code: str | EquipmentCode,
        material_batch: str | MaterialBatch,
        feeding_time: datetime,
    ) -> "MaterialInput":
        """
        Factory method with flexible input types.

        Args:
            equipment_code: Code as string or EquipmentCode
            material_batch: Batch as string or MaterialBatch
            feeding_time: When material was fed
        """
        code = equipment_code if isinstance(equipment_code, EquipmentCode) else EquipmentCode.create(equipment_code)
        batch = material_batch if isinstance(material_batch, MaterialBatch) else MaterialBatch.create(material_batch)
        return cls(code, batch, feeding_time)

    @property
    def equipment_code(self) -> EquipmentCode:
        """Device that received the material."""
        return self._equipment_code

    @property
    def material_batch(self) -> MaterialBatch:
        """Batch identifier."""
        return self._material_batch

    @property
    def feeding_time(self) -> datetime:
        """When material was fed."""
        return self._feeding_time

    def _get_equality_components(self) -> tuple:
        """Return components for equality comparison."""
        return (
            self._equipment_code,
            self._material_batch,
            self._feeding_time,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "equipment_code": str(self._equipment_code),
            "material_batch": str(self._material_batch),
            "feeding_time": self._feeding_time.isoformat(),
        }

    def __repr__(self) -> str:
        return f"MaterialInput(" f"code={self._equipment_code!r}, " f"batch={self._material_batch!r}, " f"time={self._feeding_time!r})"


__all__ = ["MaterialInput"]
