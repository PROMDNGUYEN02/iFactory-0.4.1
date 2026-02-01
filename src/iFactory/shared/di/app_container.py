"""
Main Application DI Container - Remote-First Architecture.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from iFactory.infrastructure.adapters.mssql_adapter import MssqlAdapter as MssqlDataSource
from iFactory.infrastructure.configuration.paths import PATHS
from iFactory.infrastructure.configuration.db_settings import DatabaseConfig
from iFactory.infrastructure.configuration.settings import SettingsManager

if TYPE_CHECKING:
    from iFactory.presentation.di.container import UIContainer

logger = logging.getLogger(__name__)


class AppContainer:
    """
    Main Application Container.
    Remote-First: Device status fetched directly from MSSQL.
    """

    __slots__ = (
        "_base_dir",
        "_settings",
        "_db_config",
        "_remote_data_source",
        "_ui_container",
        "_signal_bus",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir if base_dir is not None else PATHS.project_root
        self._settings = None
        self._db_config: Optional[DatabaseConfig] = None
        self._remote_data_source = None
        self._ui_container = None
        self._signal_bus = None
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return

        logger.info("[AppContainer] Initializing...")

        self._load_settings()
        await self._init_infrastructure()
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

        # Remote source only - no local caching for latest status
        if self._db_config and self._db_config.mssql_url:
            try:
                self._remote_data_source = MssqlDataSource(self._db_config.mssql_url)
                logger.info("[AppContainer] MSSQL Remote Source configured")
            except Exception as e:
                logger.warning(f"Remote data source init failed: {e}")
        else:
            logger.info("[AppContainer] MSSQL not configured - offline mode")

    def _init_presentation(self) -> None:
        from iFactory.presentation.adapters.signal_bus import SignalBus
        from iFactory.presentation.di.container import UIContainer

        self._signal_bus = SignalBus()
        self._ui_container = UIContainer(app_container=self)
        self._ui_container.initialize()

    @property
    def device_facade(self):
        """No facade needed - direct remote access."""
        return None

    @property
    def remote_source(self):
        """Get remote data source."""
        return self._remote_data_source

    @property
    def db_config(self) -> Optional[DatabaseConfig]:
        """Get database configuration."""
        return self._db_config

    def get_ui_container(self) -> Optional["UIContainer"]:
        return self._ui_container

    async def dispose(self) -> None:
        logger.info("[AppContainer] Disposing...")

        # Shutdown UI first (stops timers and async operations)
        if self._ui_container and hasattr(self._ui_container, "shutdown"):
            self._ui_container.shutdown()
            self._ui_container = None

        # Then dispose remote source
        if self._remote_data_source:
            try:
                await self._remote_data_source.dispose()
            except Exception as e:
                logger.warning(f"Error disposing remote source: {e}")
            self._remote_data_source = None

        self._initialized = False
        logger.info("[AppContainer] Disposed")

    cleanup = dispose


__all__ = ["AppContainer"]
