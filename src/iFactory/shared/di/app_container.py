# File: shared/di/app_container.py
"""
Main Application DI Container.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Dict, Any

from iFactory.infrastructure.persistence.sqlalchemy.database import (
    get_hot_engine,
    get_cold_engine,
    get_hot_session_factory,
    get_cold_session_factory,
)
from iFactory.infrastructure.persistence.sqlalchemy.unit_of_work import (
    HotStorageUnitOfWork,
    ColdStorageUnitOfWork,
    DualStorageUnitOfWork,
)
from iFactory.infrastructure.adapters.mssql_adapter import MssqlAdapter as MssqlDataSource
from iFactory.infrastructure.scheduling.task_scheduler import BackgroundScheduler
from iFactory.infrastructure.configuration.paths import PATHS
from iFactory.infrastructure.configuration.db_settings import DatabaseConfig
from iFactory.infrastructure.configuration.settings import SettingsManager
from iFactory.application.queries.devices import GetLatestDeviceStatusQuery, GetAllDevicesStatusQuery
from iFactory.application.queries.history import GetDeviceHistoryQuery, GenerateProductionTimelineQuery
from iFactory.application.commands.sync import SyncAllDevicesCommand

if TYPE_CHECKING:
    from iFactory.presentation.di.container import UIContainer
    from iFactory.presentation.adapters.signal_bus import SignalBus

logger = logging.getLogger(__name__)


class DeviceServiceAdapter:
    """
    Adapter that provides a unified interface to device operations.
    Fetches from remote MSSQL directly for Gantt data.
    """

    # Status code to name mapping
    STATUS_NAMES = {
        0: "Unknown",
        1: "Running",
        2: "Shutdown",
        3: "Stopped",
        4: "Maintenance",
        5: "Alarm",
    }

    def __init__(
        self,
        sync_cmd: Optional[SyncAllDevicesCommand],
        get_latest_qry: GetLatestDeviceStatusQuery,
        get_all_qry: GetAllDevicesStatusQuery,
        get_history_qry: GetDeviceHistoryQuery,
        gantt_qry: GenerateProductionTimelineQuery,
        remote_source: Optional[MssqlDataSource] = None,
    ):
        self._sync_cmd = sync_cmd
        self._get_latest_qry = get_latest_qry
        self._get_all_qry = get_all_qry
        self._get_history_qry = get_history_qry
        self._gantt_qry = gantt_qry
        self._remote_source = remote_source

    async def sync_device_status(self, equipment_codes=None):
        if not self._sync_cmd:
            logger.warning("Sync requested but no remote data source configured.")
            return None
        return await self._sync_cmd.execute(equipment_codes)

    async def get_device_status(self, equipment_code: str):
        return await self._get_latest_qry.execute(equipment_code)

    async def get_all_devices_status(self, equipment_codes=None):
        return await self._get_all_qry.execute(equipment_codes)

    async def get_device_history(self, equipment_code: str, days: int = 1):
        return await self._get_history_qry.execute(equipment_code, days=days)

    async def get_all_latest_status(self, equipment_codes=None):
        return await self.get_all_devices_status(equipment_codes)

    async def generate_gantt_segments(self, equipment_code: str, days: int = 1, fill_gaps: bool = True) -> Dict[str, Any]:
        """
        Generate Gantt chart segments for a device.
        FETCHES DIRECTLY FROM MSSQL for real-time data.
        Falls back to local cache if remote is unavailable.
        """
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)

        segments = []

        # Try to fetch directly from remote MSSQL first
        if self._remote_source:
            try:
                remote_history = await self._remote_source.fetch_device_history_range(equipment_code, start_time, end_time)

                if remote_history:
                    logger.info(f"Fetched {len(remote_history)} records from MSSQL for {equipment_code}")

                    for record in remote_history:
                        rec_start = record.get("start_time")
                        rec_end = record.get("end_time") or end_time
                        status_code = int(record.get("equip_status", 0))

                        # Clip to window
                        valid_start = max(rec_start, start_time) if rec_start else start_time
                        valid_end = min(rec_end, end_time)

                        if valid_start < valid_end:
                            duration = (valid_end - valid_start).total_seconds()
                            segments.append(
                                {
                                    "start_time": valid_start,
                                    "end_time": valid_end,
                                    "status_code": status_code,
                                    "status_name": self.STATUS_NAMES.get(status_code, "Unknown"),
                                    "duration_seconds": duration,
                                }
                            )

            except Exception as e:
                logger.warning(f"Failed to fetch from MSSQL for {equipment_code}: {e}")

        # Fallback to local cache if no remote data
        if not segments:
            try:
                local_segments = await self._gantt_qry.execute(equipment_code, start_time, end_time, fill_gaps)

                for dto in local_segments:
                    segments.append(
                        {
                            "start_time": dto.start_time,
                            "end_time": dto.end_time,
                            "status_code": int(dto.status_code) if dto.status_code else 0,
                            "status_name": dto.status_name,
                            "duration_seconds": dto.duration_seconds,
                        }
                    )

                if segments:
                    logger.debug(f"Used {len(segments)} segments from local cache for {equipment_code}")

            except Exception as e:
                logger.error(f"Failed to get local segments for {equipment_code}: {e}")

        return {
            "segments": segments,
            "device_code": equipment_code,
            "start": start_time,
            "end": end_time,
        }

    @property
    def is_online(self) -> bool:
        return self._remote_source is not None


class AppContainer:
    __slots__ = (
        "_base_dir",
        "_settings",
        "_db_config",
        "_hot_engine",
        "_cold_engine",
        "_hot_session_factory",
        "_cold_session_factory",
        "_remote_data_source",
        "_scheduler",
        "_cache_provider",
        "_device_service_adapter",
        "_ui_container",
        "_signal_bus",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir if base_dir is not None else PATHS.project_root
        self._settings = None
        self._db_config: Optional[DatabaseConfig] = None
        self._hot_engine = None
        self._cold_engine = None
        self._hot_session_factory = None
        self._cold_session_factory = None
        self._remote_data_source = None
        self._scheduler = None
        self._cache_provider = None
        self._device_service_adapter = None
        self._ui_container = None
        self._signal_bus = None
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
            self._settings = SettingsManager()
            self._db_config = DatabaseConfig()
        except Exception as e:
            logger.warning(f"Settings load failed: {e}")
            self._db_config = DatabaseConfig()

    async def _init_infrastructure(self) -> None:
        PATHS.ensure_directories()
        self._hot_engine = get_hot_engine()
        self._cold_engine = get_cold_engine()
        self._hot_session_factory = get_hot_session_factory()
        self._cold_session_factory = get_cold_session_factory()

        try:
            from iFactory.infrastructure.cache.memory_cache import MemoryCache

            self._cache_provider = MemoryCache(max_size=500)
            logger.info("Cache initialized")
        except Exception as e:
            logger.warning(f"Cache init failed: {e}")
            from iFactory.infrastructure.cache.memory_cache import MemoryCache

            self._cache_provider = MemoryCache(max_size=100)

        if self._db_config and self._db_config.mssql_url:
            try:
                self._remote_data_source = MssqlDataSource(self._db_config.mssql_url)
                logger.info("[AppContainer] MSSQL Remote Source configured.")
            except Exception as e:
                logger.warning(f"Remote data source init failed: {e}")
        else:
            logger.info("[AppContainer] MSSQL not configured. Running in offline/local mode.")

        if self._remote_data_source:
            self._scheduler = BackgroundScheduler(interval_seconds=3.0)

    def _create_hot_uow(self) -> HotStorageUnitOfWork:
        return HotStorageUnitOfWork(self._hot_session_factory)

    def _create_cold_uow(self) -> ColdStorageUnitOfWork:
        return ColdStorageUnitOfWork(self._cold_session_factory)

    def _create_dual_uow(self) -> DualStorageUnitOfWork:
        return DualStorageUnitOfWork(
            self._hot_session_factory,
            self._cold_session_factory,
        )

    def _init_application(self) -> None:
        if self._cache_provider is None:
            logger.error("Cache provider is None! Creating fallback.")
            from iFactory.infrastructure.cache.memory_cache import MemoryCache

            self._cache_provider = MemoryCache(max_size=100)

        get_latest_qry = GetLatestDeviceStatusQuery(
            uow_factory=self._create_hot_uow,
            cache=self._cache_provider,
        )
        get_all_qry = GetAllDevicesStatusQuery(
            uow_factory=self._create_hot_uow,
            cache=self._cache_provider,
        )
        get_history_qry = GetDeviceHistoryQuery(
            uow_factory=self._create_cold_uow,
            cache=self._cache_provider,
        )
        gantt_qry = GenerateProductionTimelineQuery(
            uow_factory=self._create_cold_uow,
            cache=self._cache_provider,
        )

        sync_cmd = None
        if self._remote_data_source:
            sync_cmd = SyncAllDevicesCommand(
                remote_source=self._remote_data_source,
                dual_uow_factory=self._create_dual_uow,
            )
            if self._scheduler:
                self._scheduler.start(lambda: sync_cmd.execute())

        # Pass remote_source to adapter for direct Gantt fetching
        self._device_service_adapter = DeviceServiceAdapter(
            sync_cmd=sync_cmd,
            get_latest_qry=get_latest_qry,
            get_all_qry=get_all_qry,
            get_history_qry=get_history_qry,
            gantt_qry=gantt_qry,
            remote_source=self._remote_data_source,  # NEW: Pass remote source
        )

    def _init_presentation(self) -> None:
        from iFactory.presentation.adapters.signal_bus import SignalBus
        from iFactory.presentation.di.container import UIContainer

        self._signal_bus = SignalBus()
        self._ui_container = UIContainer(app_container=self)
        self._ui_container.initialize()

    @property
    def device_facade(self) -> Optional[DeviceServiceAdapter]:
        return self._device_service_adapter

    def get_ui_container(self) -> Optional["UIContainer"]:
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
        if self._hot_engine:
            await self._hot_engine.dispose()
        if self._cold_engine:
            await self._cold_engine.dispose()
        self._initialized = False
        logger.info("[AppContainer] Disposed")

    cleanup = dispose


__all__ = ["AppContainer", "DeviceServiceAdapter"]
