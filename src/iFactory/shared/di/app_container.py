"""
Main Application DI Container.
Wires all layers together following Clean Architecture.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from sqlalchemy.orm import sessionmaker

# --- Infrastructure Layer Imports ---
from iFactory.infrastructure.persistence.sqlalchemy.engine import get_hot_engine
from iFactory.infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from iFactory.infrastructure.data_sources.mssql_data_source import MssqlDataSource
from iFactory.infrastructure.scheduling.background_scheduler import BackgroundScheduler

# --- Config & Path Management ---
from iFactory.infrastructure.config.app_paths import PATHS
from iFactory.infrastructure.config.db_config import DatabaseConfig

# --- Application Layer Imports ---
from iFactory.application.queries.get_latest_status import GetLatestDeviceStatusQuery
from iFactory.application.queries.get_all_devices_status import GetAllDevicesStatusQuery
from iFactory.application.queries.generate_production_timeline import GenerateProductionTimelineQuery
from iFactory.application.commands.sync_all_devices import SyncAllDevicesCommand
from iFactory.application.commands.sync_device_status import SyncDeviceStatusCommand

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from iFactory.presentation.di.ui_container import UIContainer
    from iFactory.presentation.adapters import QtSignalAdapter

logger = logging.getLogger(__name__)


class DeviceServiceAdapter:
    """Adapter to present Commands and Queries to the UIContainer."""

    def __init__(
        self,
        sync_cmd: Optional[SyncAllDevicesCommand],
        get_latest_qry: GetLatestDeviceStatusQuery,
        get_all_qry: GetAllDevicesStatusQuery,
        gantt_qry: GenerateProductionTimelineQuery,
    ):
        self._sync_cmd = sync_cmd
        self._get_latest_qry = get_latest_qry
        self._get_all_qry = get_all_qry
        self._gantt_qry = gantt_qry

    async def sync_device_status(self, equipment_codes=None):
        if not self._sync_cmd:
            logger.warning("Sync requested but no remote data source configured.")
            return None
        return await self._sync_cmd.execute(equipment_codes)

    async def get_device_status(self, equipment_code, theme="light"):
        return await self._get_latest_qry.execute(equipment_code, theme)

    async def get_all_devices_status(self, equipment_codes=None):
        return await self._get_all_qry.execute(equipment_codes)

    async def get_gantt_segments(self, equipment_code, start_time=None, end_time=None, fill_gaps=True):
        from datetime import datetime

        if end_time is None:
            end_time = datetime.now()
        if start_time is None:
            start_time = end_time.replace(hour=0, minute=0, second=0, microsecond=0)
        return await self._gantt_qry.execute(equipment_code, start_time, end_time, fill_gaps)

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
        return self._sync_cmd is not None


class AppContainer:
    """Application Dependency Injection Container."""

    __slots__ = (
        "_base_dir",
        "_settings",
        "_db_config",
        "_db_engine",
        "_uow",
        "_remote_data_source",
        "_scheduler",
        "_cache_provider",
        "_device_service_adapter",
        "_ui_container",
        "_signal_adapter",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir if base_dir is not None else PATHS.project_root
        self._settings = None
        self._db_config: Optional[DatabaseConfig] = None
        self._db_engine = None
        self._uow = None
        self._remote_data_source = None
        self._scheduler = None
        self._cache_provider = None
        self._device_service_adapter = None
        self._ui_container = None
        self._signal_adapter = None
        self._initialized = False

    async def initialize(self) -> None:
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
        try:
            from iFactory.infrastructure.config.json_manager import SettingsManager

            self._settings = SettingsManager()
            self._db_config = DatabaseConfig()
        except Exception as e:
            logger.warning(f"Settings load failed: {e}")

    async def _init_infrastructure(self) -> None:
        """Initialize Infrastructure layer: Databases, ORM, Cache, and Remote Sources."""
        from sqlalchemy.ext.asyncio import async_sessionmaker
        from iFactory.infrastructure.persistence.sqlalchemy.engine import get_hot_engine

        # 1. Ensure directories
        PATHS.ensure_directories()

        # 2. Database Engine (Async)
        self._db_engine = get_hot_engine()

        # 3. Unit of Work (Async Session)
        async_session_factory = async_sessionmaker(
            bind=self._db_engine, expire_on_commit=False, class_=__import__("sqlalchemy.ext.asyncio").ext.asyncio.AsyncSession
        )
        self._uow = SqlAlchemyUnitOfWork(async_session_factory)

        # 4. Cache (AsyncLRUCache) - [QUAN TRỌNG: Đã thêm lại đoạn này]
        try:
            from iFactory.infrastructure.cache.async_lru_cache import AsyncLRUCache

            self._cache_provider = AsyncLRUCache(max_size=500)
            logger.info("Cache initialized")
        except Exception as e:
            logger.warning(f"Cache init failed: {e}")

        # 5. Remote Data Source (MSSQL)
        if self._db_config and self._db_config.mssql_url:
            try:
                self._remote_data_source = MssqlDataSource(self._db_config.mssql_url)
                logger.info("[AppContainer] MSSQL Remote Source configured.")
            except Exception as e:
                logger.warning(f"Remote data source init failed: {e}")
        else:
            logger.info("[AppContainer] MSSQL not configured. Running in offline/local mode.")

        # 6. Scheduler
        if self._remote_data_source:
            self._scheduler = BackgroundScheduler(interval_seconds=60.0)

    def _init_application(self) -> None:
        # Check cache provider status
        if self._cache_provider is None:
            logger.error("Cache provider is None during application init! Creating fallback.")
            from iFactory.infrastructure.cache.async_lru_cache import AsyncLRUCache

            self._cache_provider = AsyncLRUCache(max_size=100)

        get_latest_qry = GetLatestDeviceStatusQuery(uow=self._uow, cache=self._cache_provider)
        get_all_qry = GetAllDevicesStatusQuery(uow=self._uow, cache=self._cache_provider)
        gantt_qry = GenerateProductionTimelineQuery(unit_of_work_factory=lambda: self._uow, cache_provider=self._cache_provider)

        sync_cmd = SyncAllDevicesCommand(remote_source=self._remote_data_source, uow=self._uow) if self._remote_data_source else None

        if self._scheduler and sync_cmd:
            self._scheduler.start(lambda: sync_cmd.execute())

        self._device_service_adapter = DeviceServiceAdapter(sync_cmd, get_latest_qry, get_all_qry, gantt_qry)

    def _init_presentation(self) -> None:
        from iFactory.presentation.adapters import QtSignalAdapter
        from iFactory.presentation.di.ui_container import UIContainer

        self._signal_adapter = QtSignalAdapter()
        self._ui_container = UIContainer(app_container=self)
        self._ui_container.initialize()

    # --- Getters ---
    @property
    def device_facade(self) -> Optional[DeviceServiceAdapter]:
        return self._device_service_adapter

    def get_ui_container(self) -> Optional[UIContainer]:
        return self._ui_container

    async def dispose(self) -> None:
        logger.info("[AppContainer] Disposing...")
        if self._scheduler:
            await self._scheduler.stop()
        if self._ui_container and hasattr(self._ui_container, "shutdown"):
            self._ui_container.shutdown()
        if self._cache_provider and hasattr(self._cache_provider, "clear"):
            await self._cache_provider.clear()
        if self._remote_data_source:
            await self._remote_data_source.dispose()
        if self._db_engine:
            await self._db_engine.dispose()
        self._initialized = False
        logger.info("[AppContainer] Disposed")

    cleanup = dispose


__all__ = ["AppContainer", "DeviceServiceAdapter"]
