"""
Infrastructure Layer Package.

This layer implements the contracts defined in the Domain Layer
and handles all external technical concerns.

Key Responsibilities:
    - Database: Engines, ORM models, connection pooling.
    - Persistence: Repository implementations and data synchronization.
    - Cache: Local and distributed caching mechanisms.
    - Managers: Coordinators for devices, charts, and UI integration (Hybrid layer).
"""

from .database import (
    BaseModel,
    HotBase,
    ColdBase,
    TimestampMixin,
    DatabaseType,
    DBConfig,
    RemoteDBParams,
    HealthStatus,
    DatabaseOrchestrator,
    DatabaseEngine,
    AsyncSQLiteEngine,
    MSSQLEngine,
    LatestStatus,
    LatestInput,
    SyncMeta,
    StatusHistory,
    InputHistory,
)
from .cache import LRUCacheStorage
from .persistence.services import SyncService
from .configuration.device_config_loader import DeviceConfigLoader

__all__ = [
    "BaseModel",
    "HotBase",
    "ColdBase",
    "TimestampMixin",
    "DatabaseType",
    "DBConfig",
    "RemoteDBParams",
    "HealthStatus",
    "DatabaseOrchestrator",
    "DatabaseEngine",
    "AsyncSQLiteEngine",
    "MSSQLEngine",
    "LatestStatus",
    "LatestInput",
    "SyncMeta",
    "StatusHistory",
    "InputHistory",
    "LRUCacheStorage",
    "SyncService",
    "DeviceConfigLoader",
]
