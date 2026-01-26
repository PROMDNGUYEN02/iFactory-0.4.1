"""
Main Application DI Container.

Wires all layers together following Clean Architecture.
This is the ONLY place where all layers know about each other.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

# --- Infrastructure Layer Imports ---
from iFactory.infrastructure.database.engine import AsyncDatabaseEngine
from iFactory.infrastructure.persistence.uow import SqliteUnitOfWork
from iFactory.infrastructure.remote.mssql_data_source import MssqlDataSource
from iFactory.infrastructure.sync.sync_orchestrator import SyncOrchestrator

# --- Application Layer Imports ---
from iFactory.application.use_cases.device.get_latest_status import GetLatestDeviceStatusUseCase
from iFactory.application.use_cases.device.get_all_devices_status import GetAllDevicesStatusUseCase
from iFactory.application.use_cases.production.generate_production_timeline import GenerateProductionTimelineUseCase
from iFactory.application.use_cases.sync.sync_all_devices_use_case import SyncAllDevicesUseCase

if TYPE_CHECKING:
    from iFactory.presentation.qt.di import UIContainer
    from iFactory.presentation.adapters import QtSignalAdapter

logger = logging.getLogger(__name__)


# ==============================================================================
# Adapter: Bridges the gap between UI expectations and new Use Cases
# ==============================================================================
class DeviceServiceAdapter:
    """
    Adapter to present Use Cases to the UIContainer using the old service interface.
    """

    def __init__(
        self,
        sync_uc: Optional[SyncAllDevicesUseCase],
        get_latest_uc: GetLatestDeviceStatusUseCase,
        get_all_uc: GetAllDevicesStatusUseCase,
        gantt_uc: GenerateProductionTimelineUseCase,
    ):
        self._sync_uc = sync_uc
        self._get_latest_uc = get_latest_uc
        self._get_all_uc = get_all_uc
        self._gantt_uc = gantt_uc

    async def sync_device_status(self, equipment_codes=None):
        if not self._sync_uc:
            logger.warning("Sync requested but no remote data source configured.")
            return None
        return await self._sync_uc.execute(equipment_codes)

    async def get_device_status(self, equipment_code, theme="light"):
        return await self._get_latest_uc.execute(equipment_code, theme)

    async def get_all_devices_status(self, equipment_codes=None):
        return await self._get_all_uc.execute(equipment_codes)

    async def get_gantt_segments(self, equipment_code, start_time=None, end_time=None, fill_gaps=True):
        from datetime import datetime

        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)

        return await self._gantt_uc.execute(equipment_code, start_time, end_time, fill_gaps)

    async def get_all_latest_status(self, equipment_codes=None):
        return await self.get_all_devices_status(equipment_codes)

    async def generate_gantt_segments(self, equipment_code, days=1, fill_gaps=True):
        from datetime import datetime, timedelta

        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        segments = await self.get_gantt_segments(equipment_code, start_time, end_time, fill_gaps)
        return {"segments": segments, "start": start_time, "end": end_time}

    @property
    def is_online(self):
        return self._sync_uc is not None


# ==============================================================================
# Main Container
# ==============================================================================
class AppContainer:
    """
    Application Dependency Injection Container.
    """

    __slots__ = (
        "_base_dir",
        "_settings",
        "_db_engine",
        "_uow",
        "_remote_data_source",
        "_sync_orchestrator",
        "_cache_provider",
        "_device_service_adapter",
        "_ui_container",
        "_signal_adapter",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        from iFactory.shared.utils.paths import get_project_root

        self._base_dir = base_dir if base_dir is not None else get_project_root()

        self._settings = None
        self._db_engine: Optional[AsyncDatabaseEngine] = None
        self._uow: Optional[SqliteUnitOfWork] = None
        self._remote_data_source: Optional[MssqlDataSource] = None
        self._sync_orchestrator: Optional[SyncOrchestrator] = None
        self._cache_provider = None

        self._device_service_adapter: Optional[DeviceServiceAdapter] = None
        self._ui_container: Optional[UIContainer] = None
        self._signal_adapter: Optional[QtSignalAdapter] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all components in correct dependency order."""
        if self._initialized:
            return

        logger.info("[AppContainer] Initializing Clean Architecture stack...")
        self._load_settings()
        await self._init_infrastructure()
        self._init_application()
        self._init_presentation()
        self._initialized = True
        logger.info("[AppContainer] Initialization complete")

    def _load_settings(self) -> None:
        """Load application settings."""
        try:
            from iFactory.config import SettingsManager

            self._settings = SettingsManager()
        except Exception as e:
            logger.warning(f"Settings load failed: {e}")

    async def _init_infrastructure(self) -> None:
        """Initialize Infrastructure layer: Databases, ORM, and Remote Sources."""

        # 1. Local Database (SQLite)
        db_path = self._settings.database.hot_store_path if self._settings and hasattr(self._settings, "database") else "data/hot_store.db"
        self._db_engine = AsyncDatabaseEngine(f"sqlite+aiosqlite:///{db_path}")
        await self._db_engine.init_db()

        # 2. Persistence Layer (Unit of Work)
        self._uow = SqliteUnitOfWork(self._db_engine.get_session_factory())

        # 3. Cache
        try:
            from iFactory.infrastructure.cache.cache_provider import InMemoryCacheProvider

            self._cache_provider = InMemoryCacheProvider(max_size=500)
        except Exception as e:
            logger.warning(f"Cache init failed: {e}")

        # 4. Remote Data Source (MSSQL)
        if self._settings and hasattr(self._settings, "db_settings"):
            db_cfg = self._settings.db_settings
            mssql_conn_string = (
                f"mssql+aioodbc://{db_cfg.mssql_user}:{db_cfg.mssql_password}@{db_cfg.mssql_host}/{db_cfg.mssql_db}?driver={db_cfg.mssql_driver}"
            )
            try:
                self._remote_data_source = MssqlDataSource(mssql_conn_string)
            except Exception as e:
                logger.warning(f"Remote data source init failed: {e}")

        # 5. Sync Subdomain
        if self._remote_data_source:
            self._sync_orchestrator = SyncOrchestrator(data_source=self._remote_data_source, uow=self._uow)

    def _init_application(self) -> None:
        """
        Initialize Application layer, injecting the Infrastructure (UoW, Remote Source) into Use Cases.
        """
        # FIX: The Device Use Cases expect 'cache' as the keyword argument, not 'cache_provider'
        get_latest_uc = GetLatestDeviceStatusUseCase(uow=self._uow, cache=self._cache_provider)
        get_all_uc = GetAllDevicesStatusUseCase(uow=self._uow, cache=self._cache_provider)

        # FIX: The Production/Gantt Use Case expects 'unit_of_work_factory' and 'cache_provider'
        gantt_uc = GenerateProductionTimelineUseCase(unit_of_work_factory=lambda: self._uow, cache_provider=self._cache_provider)

        sync_uc = SyncAllDevicesUseCase(remote_source=self._remote_data_source, uow=self._uow) if self._remote_data_source else None

        # Bind to Presentation Adapter
        self._device_service_adapter = DeviceServiceAdapter(sync_uc, get_latest_uc, get_all_uc, gantt_uc)

    def _init_presentation(self) -> None:
        """Initialize Presentation layer."""
        from iFactory.presentation.adapters import QtSignalAdapter
        from iFactory.presentation.qt.di import UIContainer

        self._signal_adapter = QtSignalAdapter()
        self._ui_container = UIContainer(
            device_service=self._device_service_adapter,
            signal_adapter=self._signal_adapter,
            settings=self._settings,
        )

    # --- Getters ---

    def get_ui_container(self) -> Optional[UIContainer]:
        return self._ui_container

    @property
    def is_online(self) -> bool:
        """Check if running in online mode (Remote DB connected)."""
        return self._remote_data_source is not None

    def get_status(self) -> Dict[str, bool]:
        """Get container status information."""
        return {
            "initialized": self._initialized,
            "has_settings": self._settings is not None,
            "sqlite_connected": self._db_engine is not None,
            "mssql_connected": self._remote_data_source is not None,
            "sync_available": self._sync_orchestrator is not None,
            "cache_enabled": self._cache_provider is not None,
            "online_mode": self.is_online,
        }

    async def dispose(self) -> None:
        """Dispose all resources gracefully."""
        logger.info("[AppContainer] Disposing...")

        if self._ui_container and hasattr(self._ui_container, "cleanup"):
            self._ui_container.cleanup()

        if self._cache_provider and hasattr(self._cache_provider, "clear"):
            self._cache_provider.clear()

        if self._remote_data_source:
            await self._remote_data_source.dispose()

        if self._db_engine:
            await self._db_engine.dispose()

        self._initialized = False
        logger.info("[AppContainer] Disposed")

    cleanup = dispose


__all__ = ["AppContainer"]
