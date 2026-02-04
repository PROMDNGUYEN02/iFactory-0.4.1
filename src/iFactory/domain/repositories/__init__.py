# src/iFactory/domain/repositories/__init__.py
"""
Domain Repository Interfaces (Ports).

Repositories are abstractions for aggregate persistence.
These are ports that the infrastructure layer implements.

Pattern: Repository Pattern + Dependency Inversion
- Domain defines interfaces (what it needs)
- Infrastructure provides implementations (how it's done)
"""

from .device_repository import DeviceRepository
from .production_repository import ProductionRepository, HistoryRecord, OEEMetrics

__all__ = [
    "DeviceRepository",
    "ProductionRepository",
    "HistoryRecord",
    "OEEMetrics",
]
