"""
Database infrastructure module.

Provides:
    - Base classes for ORM models
    - Database configuration
    - SQLite and MSSQL engines
    - Database orchestrator
    - ORM models for hot and cold stores
"""

from .base import BaseModel, HotBase, ColdBase, TimestampMixin
from .config import DatabaseType, DBConfig, RemoteDBParams, HealthStatus
from .orchestrator import DatabaseOrchestrator
from .engines import DatabaseEngine, EngineConfig, AsyncSQLiteEngine, MSSQLEngine
from .models import LatestStatus, LatestInput, SyncMeta, StatusHistory, InputHistory

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
    "EngineConfig",
    "AsyncSQLiteEngine",
    "MSSQLEngine",
    "LatestStatus",
    "LatestInput",
    "SyncMeta",
    "StatusHistory",
    "InputHistory",
]
