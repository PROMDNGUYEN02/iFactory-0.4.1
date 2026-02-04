# src/iFactory/domain/value_objects/material_input.py
"""
Material Input Value Object.

Represents a feeding event of raw materials into a machine.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ..common.value_object import ValueObject
from .equipment_code import EquipmentCode
from .material_batch import MaterialBatch


class MaterialInput(ValueObject):
    """
    Represents a feeding event of raw materials into a machine.

    This is an immutable record of material consumption that can be
    used for traceability, inventory management, and quality control.

    Usage:
        # Direct creation
        input_record = MaterialInput(
            equipment_code=EquipmentCode.create("CNC-001"),
            material_batch=MaterialBatch.create("LOT-2024-001"),
            feeding_time=datetime.now()
        )

        # Factory method with strings
        input_record = MaterialInput.create(
            equipment_code="CNC-001",
            material_batch="LOT-2024-001",
            feeding_time=datetime.now()
        )
    """

    __slots__ = (
        "_equipment_code",
        "_material_batch",
        "_feeding_time",
        "_quantity",
        "_operator_id",
    )

    def __init__(
        self,
        equipment_code: EquipmentCode,
        material_batch: MaterialBatch,
        feeding_time: datetime,
        quantity: Optional[float] = None,
        operator_id: Optional[str] = None,
    ) -> None:
        """
        Create MaterialInput record.

        Args:
            equipment_code: Device that received the material
            material_batch: Batch identifier
            feeding_time: When material was fed
            quantity: Amount of material (optional)
            operator_id: ID of operator who fed material (optional)
        """
        object.__setattr__(self, "_equipment_code", equipment_code)
        object.__setattr__(self, "_material_batch", material_batch)
        object.__setattr__(self, "_feeding_time", feeding_time)
        object.__setattr__(self, "_quantity", quantity)
        object.__setattr__(self, "_operator_id", operator_id)

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def create(
        cls,
        equipment_code: str | EquipmentCode,
        material_batch: str | MaterialBatch,
        feeding_time: datetime,
        quantity: Optional[float] = None,
        operator_id: Optional[str] = None,
    ) -> "MaterialInput":
        """
        Factory method with flexible input types.

        Args:
            equipment_code: Code as string or EquipmentCode
            material_batch: Batch as string or MaterialBatch
            feeding_time: When material was fed
            quantity: Amount of material (optional)
            operator_id: Operator ID (optional)
        """
        code = equipment_code if isinstance(equipment_code, EquipmentCode) else EquipmentCode.create(equipment_code)
        batch = material_batch if isinstance(material_batch, MaterialBatch) else MaterialBatch.create(material_batch)
        return cls(code, batch, feeding_time, quantity, operator_id)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaterialInput":
        """
        Deserialize from dictionary.

        Args:
            data: Dictionary with keys: equipment_code, material_batch,
                  feeding_time, quantity (optional), operator_id (optional)
        """
        feeding_time = data["feeding_time"]
        if isinstance(feeding_time, str):
            feeding_time = datetime.fromisoformat(feeding_time)

        return cls.create(
            equipment_code=data["equipment_code"],
            material_batch=data["material_batch"],
            feeding_time=feeding_time,
            quantity=data.get("quantity"),
            operator_id=data.get("operator_id"),
        )

    # ========================================================================
    # Properties
    # ========================================================================

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

    @property
    def quantity(self) -> Optional[float]:
        """Amount of material fed."""
        return self._quantity

    @property
    def operator_id(self) -> Optional[str]:
        """ID of operator who fed material."""
        return self._operator_id

    # ========================================================================
    # Derived Properties
    # ========================================================================

    @property
    def has_quantity(self) -> bool:
        """True if quantity was recorded."""
        return self._quantity is not None

    @property
    def date(self) -> datetime:
        """Date portion of feeding time."""
        return self._feeding_time.replace(hour=0, minute=0, second=0, microsecond=0)

    # ========================================================================
    # Equality
    # ========================================================================

    def _get_equality_components(self) -> Tuple[Any, ...]:
        """Return components for equality comparison."""
        return (
            self._equipment_code,
            self._material_batch,
            self._feeding_time,
        )

    # ========================================================================
    # Serialization
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result = {
            "equipment_code": str(self._equipment_code),
            "material_batch": str(self._material_batch),
            "feeding_time": self._feeding_time.isoformat(),
        }
        if self._quantity is not None:
            result["quantity"] = self._quantity
        if self._operator_id is not None:
            result["operator_id"] = self._operator_id
        return result

    def __repr__(self) -> str:
        parts = [
            f"code={self._equipment_code!r}",
            f"batch={self._material_batch!r}",
            f"time={self._feeding_time.isoformat()!r}",
        ]
        if self._quantity is not None:
            parts.append(f"qty={self._quantity}")
        return f"MaterialInput({', '.join(parts)})"


__all__ = ["MaterialInput"]
