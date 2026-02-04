# src/iFactory/domain/value_objects/__init__.py
"""
Domain Value Objects.

Value Objects are immutable objects that are distinguished by their
attributes rather than identity. Two value objects with the same
attributes are considered equal.
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
