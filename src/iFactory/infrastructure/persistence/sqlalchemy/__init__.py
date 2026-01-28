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
from .mapper import OrmDeviceMapper
from .unit_of_work import (
    HotStorageUnitOfWork,
    ColdStorageUnitOfWork,
    DualStorageUnitOfWork,
)

# REPOSITORIES: Fixed imports to match new split-file structure
from .repositories.hot_repository import HotRepository as HotStorageRepository
from .repositories.cold_repository import ColdRepository as ColdStorageRepository

# Alias for backward compatibility if needed
SqlAlchemyDeviceRepository = HotStorageRepository
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
    "OrmDeviceMapper",
    # Repositories
    "HotStorageRepository",
    "ColdStorageRepository",
    "SqlAlchemyDeviceRepository",
    # Unit of Work
    "HotStorageUnitOfWork",
    "ColdStorageUnitOfWork",
    "DualStorageUnitOfWork",
    "SqlAlchemyUnitOfWork",
]
