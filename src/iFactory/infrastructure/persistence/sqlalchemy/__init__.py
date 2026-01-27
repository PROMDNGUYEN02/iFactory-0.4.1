"""
SQLAlchemy persistence infrastructure.
Supports dual storage: Hot (latest) and Cold (history).
"""

from .engine import (
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
from .mappers import OrmDeviceMapper
from .database import HotStorageRepository, ColdStorageRepository
from .uow import (
    HotStorageUnitOfWork,
    ColdStorageUnitOfWork,
    DualStorageUnitOfWork,
)

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
