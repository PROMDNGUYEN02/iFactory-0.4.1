"""
Main Application DI Container.

Wires all layers together following Clean Architecture.
This is the ONLY place where all layers know about each other.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional
from types import TracebackType

if TYPE_CHECKING:
    from iFactory.presentation.qt.di import UIContainer
    from iFactory.infrastructure.database.orchestrator import DatabaseOrchestrator
    from iFactory.infrastructure.persistence.data_sources import MssqlDataSource
    from iFactory.infrastructure.persistence.services import (
        SyncOrchestrator,
        SyncService,
    )
    from iFactory.presentation.adapters import QtSignalAdapter

logger = logging.getLogger(__name__)


# ==============================================================================
# Adapter: Bridges the gap between UI expectations and new Use Cases
# ==============================================================================
class DeviceServiceAdapter:
    """
    Adapter to present Use Cases to the UIContainer using the old service interface.
    This prevents massive changes in the Presentation layer.
    """

    def __init__(
        self,
        sync_uc,
        get_latest_uc,
        get_all_uc,
        gantt_uc,
    ):
        self._sync_uc = sync_uc
        self._get_latest_uc = get_latest_uc
        self._get_all_uc = get_all_uc
        self._gantt_uc = gantt_uc

    async def sync_device_status(self, equipment_codes=None):
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

    # Backward compatibility aliases used by controllers
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
# Simple UnitOfWork Implementation
# ==============================================================================
class SimpleUnitOfWork:
    """
    Minimal UnitOfWork implementation to satisfy Use Cases.
    Updated to support the consolidated domain repositories.
    """

    def __init__(self, device_repo, production_repo):
        self.devices = device_repo
        self.production = production_repo

    async def __aenter__(self):
        return self

    async def __aexit__(
        self,
        exc_type: Optional[type],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ):
        pass

    async def commit(self):
        pass


# ==============================================================================
# Main Container
# ==============================================================================
class AppContainer:
    """
    Application Dependency Injection Container.
    """

    __slots__ = (
        "_base_dir",
        "_db_config",
        "_settings",
        "_db_orchestrator",
        "_sync_orchestrator",
        "_sync_service",
        "_remote_data_source",
        "_cache_provider",
        "_device_service_adapter",
        "_summary_provider",
        "_right_menu_provider",
        "_ui_container",
        "_signal_adapter",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        from iFactory.shared.utils.paths import get_project_root

        if base_dir is None:
            self._base_dir = get_project_root()
        else:
            self._base_dir = base_dir

        from iFactory.infrastructure.database.config import DBConfig

        self._db_config = DBConfig.production()
        self._settings = None
        self._db_orchestrator: Optional[DatabaseOrchestrator] = None
        self._sync_orchestrator: Optional[SyncOrchestrator] = None
        self._sync_service: Optional[SyncService] = None
        self._remote_data_source: Optional[MssqlDataSource] = None
        self._cache_provider = None
        self._device_service_adapter: Optional[DeviceServiceAdapter] = None
        self._summary_provider = None
        self._right_menu_provider = None
        self._ui_container: Optional[UIContainer] = None
        self._signal_adapter: Optional[QtSignalAdapter] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all components in correct order."""
        if self._initialized:
            return
        logger.info("[AppContainer] Initializing...")
        self._load_settings()
        await self._init_infrastructure()
        await self._init_sync()
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
        """Initialize infrastructure layer."""
        from iFactory.infrastructure.database.orchestrator import DatabaseOrchestrator

        remote_params = self._build_remote_params()
        self._db_orchestrator = DatabaseOrchestrator(base_dir=self._base_dir, remote=remote_params, config=self._db_config)
        await self._db_orchestrator.initialize()

        try:
            from iFactory.infrastructure.cache import InMemoryCacheProvider

            self._cache_provider = InMemoryCacheProvider(max_size=500)
        except Exception as e:
            logger.warning(f"Cache init failed: {e}")

        if self._db_orchestrator.mssql.is_connected:
            try:
                from iFactory.infrastructure.persistence.data_sources import MssqlDataSource

                self._remote_data_source = MssqlDataSource(self._db_orchestrator.mssql)
            except Exception as e:
                logger.warning(f"Remote data source failed: {e}")

    def _build_remote_params(self) -> Optional[Any]:
        """Build remote database parameters from settings."""
        if not self._settings:
            return None
        try:
            db_cfg = self._settings.db_settings
            required = (db_cfg.mssql_host, db_cfg.mssql_db, db_cfg.mssql_user)
            if not all((f and str(f).strip() for f in required)):
                return None
            from iFactory.infrastructure.database.config import RemoteDBParams

            return RemoteDBParams(
                host=db_cfg.mssql_host,
                database=db_cfg.mssql_db,
                user=db_cfg.mssql_user,
                password=db_cfg.mssql_password,
                driver=db_cfg.mssql_driver,
                encrypt=True,
                trust_cert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to build remote params: {e}")
            return None

    async def _init_sync(self) -> None:
        """Initialize sync service and orchestrator."""
        if not self._remote_data_source:
            logger.info("Sync disabled (no remote data source)")
            return
        try:
            from iFactory.infrastructure.persistence.services import SyncOrchestrator, SyncService
            from iFactory.infrastructure.persistence.repositories import SqliteDeviceRepository, SqliteProductionRepository

            device_repo = SqliteDeviceRepository(self._db_orchestrator.hot)
            production_repo = SqliteProductionRepository(self._db_orchestrator.hot, self._db_orchestrator.cold)
            uow = SimpleUnitOfWork(device_repo, production_repo)

            self._sync_service = SyncService(
                db=uow,
                data_source=self._remote_data_source,
                history_interval=300,
            )
            await self._sync_service.initialize()

            self._sync_orchestrator = SyncOrchestrator(
                db=self._db_orchestrator,
                sync_service=self._sync_service,
                status_interval=3.0,
                input_interval=3.0,
                history_interval=5.0,
            )
            await self._sync_orchestrator.start()
            logger.info("Sync Orchestrator started")
        except Exception as e:
            logger.warning(f"Sync init failed: {e}")
            self._sync_service = None
            self._sync_orchestrator = None

    def _init_application(self) -> None:
        """
        Initialize application layer using Use Cases directly.
        """
        from iFactory.application.use_cases import (
            GenerateProductionTimelineUseCase,
            GetAllDevicesStatusUseCase,
            GetLatestDeviceStatusUseCase,
        )
        from iFactory.application.use_cases.sync.sync_all_devices_use_case import (
            SyncAllDevicesUseCase,
        )
        from iFactory.application.services.summary_provider import SummaryDataProvider
        from iFactory.application.services.right_menu_provider import RightMenuDataProvider
        from iFactory.infrastructure.persistence.repositories import (
            SqliteDeviceRepository,
            SqliteProductionRepository,
        )

        hot = self._db_orchestrator.hot
        cold = self._db_orchestrator.cold

        # Repositories
        device_repo = SqliteDeviceRepository(hot)
        production_repo = SqliteProductionRepository(hot, cold)

        # Use Cases
        sync_uc = SyncAllDevicesUseCase(self._remote_data_source, device_repo) if self._remote_data_source else None

        get_latest_uc = GetLatestDeviceStatusUseCase(SimpleUnitOfWork(device_repo, production_repo), self._cache_provider)

        get_all_uc = GetAllDevicesStatusUseCase(SimpleUnitOfWork(device_repo, production_repo), self._cache_provider)

        gantt_uc = GenerateProductionTimelineUseCase(
            unit_of_work_factory=lambda: SimpleUnitOfWork(device_repo, production_repo), cache_provider=self._cache_provider
        )

        # Application Services
        self._summary_provider = SummaryDataProvider(production_repo)
        self._right_menu_provider = RightMenuDataProvider(production_repo)

        # Wrap Use Cases in Adapter for UI compatibility
        self._device_service_adapter = DeviceServiceAdapter(sync_uc, get_latest_uc, get_all_uc, gantt_uc)

    def _init_presentation(self) -> None:
        """Initialize presentation layer."""
        from iFactory.presentation.adapters import QtSignalAdapter
        from iFactory.presentation.qt.di import UIContainer

        self._signal_adapter = QtSignalAdapter()
        self._ui_container = UIContainer(
            device_service=self._device_service_adapter,
            signal_adapter=self._signal_adapter,
            settings=self._settings,
        )

    def get_device_service(self) -> Optional[DeviceServiceAdapter]:
        return self._device_service_adapter

    def get_sync_service(self) -> Optional[SyncService]:
        return self._sync_service

    def get_ui_container(self) -> Optional[UIContainer]:
        return self._ui_container

    def get_signal_adapter(self) -> Optional[QtSignalAdapter]:
        return self._signal_adapter

    def get_remote_data_source(self) -> Optional[MssqlDataSource]:
        return self._remote_data_source

    def get_summary_provider(self) -> Optional[SummaryDataProvider]:
        return self._summary_provider

    def get_right_menu_provider(self) -> Optional[RightMenuDataProvider]:
        return self._right_menu_provider

    @property
    def hot_engine(self):
        return self._db_orchestrator.hot if self._db_orchestrator else None

    @property
    def cold_engine(self):
        return self._db_orchestrator.cold if self._db_orchestrator else None

    @property
    def mssql_engine(self):
        return self._db_orchestrator.mssql if self._db_orchestrator else None

    def get_status(self) -> Dict[str, bool]:
        """Get container status information."""
        db_init = self._db_orchestrator.is_initialized if self._db_orchestrator else False
        remote_conn = self._db_orchestrator.is_remote_connected if self._db_orchestrator else False
        return {
            "initialized": self._initialized,
            "has_settings": self._settings is not None,
            "sqlite_connected": db_init,
            "mssql_connected": remote_conn,
            "sync_available": self._sync_service is not None,
            "cache_enabled": self._cache_provider is not None,
            "online_mode": self._remote_data_source is not None,
        }

    @property
    def is_online(self) -> bool:
        """Check if running in online mode."""
        return self._remote_data_source is not None

    async def dispose(self) -> None:
        """Dispose all resources."""
        logger.info("[AppContainer] Disposing...")
        if self._sync_orchestrator:
            try:
                await self._sync_orchestrator.stop()
            except Exception as e:
                logger.warning(f"Sync stop error: {e}")
        if self._ui_container and hasattr(self._ui_container, "cleanup"):
            try:
                self._ui_container.cleanup()
            except Exception as e:
                logger.warning(f"UI cleanup error: {e}")
        if self._cache_provider:
            try:
                if hasattr(self._cache_provider, "stop"):
                    await self._cache_provider.stop()
                elif hasattr(self._cache_provider, "clear"):
                    self._cache_provider.clear()
            except Exception as e:
                logger.warning(f"Cache cleanup error: {e}")
        if self._db_orchestrator:
            try:
                await self._db_orchestrator.dispose()
            except Exception as e:
                logger.warning(f"DB cleanup error: {e}")
        self._initialized = False
        logger.info("[AppContainer] Disposed")

    cleanup = dispose


__all__ = ["AppContainer"]
