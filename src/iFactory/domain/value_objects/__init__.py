# src/iFactory/domain/value_objects/__init__.py
"""
Domain Value Objects.

Value objects are immutable domain concepts defined by their attributes
rather than identity. They are:
- Immutable (cannot be changed after creation)
- Self-validating (validate on construction)
- Comparable by value (not identity)
- Interchangeable when equal
"""

from .equipment_code import EquipmentCode
from .material_batch import MaterialBatch
from .material_input import MaterialInput
from .status_period import StatusPeriod
from .time_range import TimeRange

__all__ = [
    "EquipmentCode",
    "MaterialBatch",
    "MaterialInput",
    "StatusPeriod",
    "TimeRange",
]
