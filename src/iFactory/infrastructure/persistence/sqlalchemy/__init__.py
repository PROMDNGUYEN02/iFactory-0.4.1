# File: infrastructure/persistence/sqlalchemy/__init__.py
"""
SQLAlchemy persistence infrastructure.
Supports dual storage: Hot (latest) and Cold (history).
"""

from .database import (
    # Class-based API
    DatabaseManager,
    # Functional API
    get_storage_engine,
    get_hot_engine,
    get_cold_engine,
    get_hot_session_factory,
    get_cold_session_factory,
    get_mssql_engine,
)
from .models import (
    Base,
    HotBase,
    ColdBase,
    DeviceModel,
    LatestMaterialInputModel,
    StatusHistoryModel,
    MaterialInputHistoryModel,
    MaterialInputModel,
)
from .mapper import SQLAlchemyMapper
from .unit_of_work import (
    HotStorageUnitOfWork,
    ColdStorageUnitOfWork,
    DualStorageUnitOfWork,
)
from .repositories.device_repository import SqlAlchemyDeviceRepository
from .repositories.production_repository import SqlAlchemyProductionRepository

# Aliases for backward compatibility
OrmDeviceMapper = SQLAlchemyMapper
HotStorageRepository = SqlAlchemyDeviceRepository
ColdStorageRepository = SqlAlchemyProductionRepository
SqlAlchemyUnitOfWork = HotStorageUnitOfWork

__all__ = [
    # Database Manager
    "DatabaseManager",
    # Engines
    "get_storage_engine",
    "get_hot_engine",
    "get_cold_engine",
    "get_hot_session_factory",
    "get_cold_session_factory",
    "get_mssql_engine",
    # Base classes
    "Base",
    "HotBase",
    "ColdBase",
    # Models
    "DeviceModel",
    "LatestMaterialInputModel",
    "StatusHistoryModel",
    "MaterialInputHistoryModel",
    "MaterialInputModel",
    # Mapper
    "SQLAlchemyMapper",
    "OrmDeviceMapper",
    # Repositories
    "HotStorageRepository",
    "ColdStorageRepository",
    "SqlAlchemyDeviceRepository",
    "SqlAlchemyProductionRepository",
    # Unit of Work
    "HotStorageUnitOfWork",
    "ColdStorageUnitOfWork",
    "DualStorageUnitOfWork",
    "SqlAlchemyUnitOfWork",
]
