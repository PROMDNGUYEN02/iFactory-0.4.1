# src/iFactory/domain/repositories/__init__.py
"""
Domain Repository Interfaces.
"""

from .device_repository import DeviceRepository
from .production_repository import HistoryRecord, ProductionRepository


__all__ = [
    "DeviceRepository",
    "HistoryRecord",
    "ProductionRepository",
]
