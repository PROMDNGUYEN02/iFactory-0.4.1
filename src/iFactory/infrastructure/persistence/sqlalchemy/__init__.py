"""
SQLAlchemy persistence infrastructure.
Supports dual storage: Hot (latest) and Cold (history).
"""

from .database import (
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
    StatusPeriodModel,
    MaterialInputHistoryModel,
    MaterialInputModel,
)

# Import from .mapper (singular) to match file system
from .mapper import SQLAlchemyMapper

# Alias for backward compatibility
OrmDeviceMapper = SQLAlchemyMapper

from .unit_of_work import (
    HotStorageUnitOfWork,
    ColdStorageUnitOfWork,
    DualStorageUnitOfWork,
)

# REPOSITORIES
from .repositories.device_repository import SqlAlchemyDeviceRepository
from .repositories.production_repository import SqlAlchemyProductionRepository

# Aliases
HotStorageRepository = SqlAlchemyDeviceRepository
ColdStorageRepository = SqlAlchemyProductionRepository
SqlAlchemyUnitOfWork = HotStorageUnitOfWork

__all__ = [
    # Engines
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
    "StatusPeriodModel",
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
