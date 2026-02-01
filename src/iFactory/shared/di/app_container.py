# File: shared/di/app_container.py
"""
Main Application DI Container - Remote-First Architecture with New Sync API.

Wires up Application Layer components (SyncOrchestrator, Handlers) and
provides them to the Presentation Layer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable

from iFactory.infrastructure.adapters.mssql_adapter import MssqlAdapter as MssqlDataSource
from iFactory.infrastructure.configuration.paths import PATHS
from iFactory.infrastructure.configuration.db_settings import DatabaseConfig
from iFactory.infrastructure.configuration.settings import SettingsManager

if TYPE_CHECKING:
    from iFactory.presentation.di.container import UIContainer
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator
    from iFactory.application.ports.uow import AbstractUnitOfWork

logger = logging.getLogger(__name__)


class AppContainer:
    """
    Main Application Container.

    Responsibilities:
    - Initialize infrastructure components (remote source, databases)
    - Create Application Layer services (SyncOrchestrator)
    - Provide dependencies to Presentation Layer

    Architecture:
    - Remote-First: Device status fetched directly from MSSQL
    - New Sync API: SyncOrchestrator receives explicit device IDs
    """

    __slots__ = (
        "_base_dir",
        "_settings",
        "_db_config",
        "_remote_data_source",
        "_sync_orchestrator",
        "_uow_factory",
        "_ui_container",
        "_signal_bus",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir if base_dir is not None else PATHS.project_root
        self._settings = None
        self._db_config: Optional[DatabaseConfig] = None
        self._remote_data_source = None
        self._sync_orchestrator: Optional["SyncOrchestrator"] = None
        self._uow_factory: Optional[Callable[[], "AbstractUnitOfWork"]] = None
        self._ui_container = None
        self._signal_bus = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize all container components."""
        if self._initialized:
            return

        logger.info("[AppContainer] Initializing...")

        self._load_settings()
        await self._init_infrastructure()
        self._init_application_layer()
        self._init_presentation()

        self._initialized = True
        logger.info("[AppContainer] Initialization complete")

    def _load_settings(self) -> None:
        """Load application settings."""
        try:
            self._settings = SettingsManager()
            self._db_config = DatabaseConfig()
        except Exception as e:
            logger.warning(f"Settings load failed: {e}")
            self._db_config = DatabaseConfig()

    async def _init_infrastructure(self) -> None:
        """Initialize infrastructure components."""
        PATHS.ensure_directories()

        # Initialize remote source
        if self._db_config and self._db_config.mssql_url:
            try:
                self._remote_data_source = MssqlDataSource(self._db_config.mssql_url)
                logger.info("[AppContainer] MSSQL Remote Source configured")
            except Exception as e:
                logger.warning(f"Remote data source init failed: {e}")
        else:
            logger.info("[AppContainer] MSSQL not configured - offline mode")

        # Initialize UoW factory if needed for history caching
        await self._init_uow_factory()

    async def _init_uow_factory(self) -> None:
        """Initialize Unit of Work factory for local caching (optional)."""
        try:
            from iFactory.infrastructure.persistence.sqlalchemy.unit_of_work import (
                SqlAlchemyUnitOfWork,
            )
            from iFactory.infrastructure.persistence.sqlalchemy.database import (
                DatabaseManager,
            )

            # Initialize database for history caching
            if self._db_config and self._db_config.sqlite_url:
                db_manager = DatabaseManager(self._db_config.sqlite_url)
                await db_manager.initialize()

                self._uow_factory = lambda: SqlAlchemyUnitOfWork(db_manager.session_factory)
                logger.info("[AppContainer] UoW factory configured for history caching")
            else:
                self._uow_factory = None
                logger.info("[AppContainer] No local database - history caching disabled")

        except Exception as e:
            logger.warning(f"UoW factory init failed: {e}")
            self._uow_factory = None

    def _init_application_layer(self) -> None:
        """Initialize Application Layer services."""
        if not self._remote_data_source:
            logger.warning("[AppContainer] No remote source - sync orchestrator disabled")
            return

        try:
            from iFactory.application.services.sync_orchestrator import (
                create_sync_orchestrator,
            )

            # Create sync orchestrator with dependencies
            self._sync_orchestrator = create_sync_orchestrator(
                remote_source=self._remote_data_source,
                uow_factory=self._uow_factory or self._create_null_uow_factory(),
                on_sync_complete=self._on_sync_complete,
            )

            logger.info("[AppContainer] SyncOrchestrator configured")

        except Exception as e:
            logger.error(f"SyncOrchestrator init failed: {e}")
            self._sync_orchestrator = None

    def _create_null_uow_factory(self) -> Callable:
        """Create a no-op UoW factory when no local database is available."""
        from iFactory.application.ports.uow import AbstractUnitOfWork

        class NullUnitOfWork(AbstractUnitOfWork):
            """No-op UoW for when local caching is disabled."""

            devices = None
            history = None

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                pass

            async def commit(self):
                pass

            async def rollback(self):
                pass

        return lambda: NullUnitOfWork()

    def _on_sync_complete(self, result) -> None:
        """Handle sync completion from orchestrator."""
        logger.debug(f"[AppContainer] Sync completed: {result.count} devices")
        # Could emit to signal bus if needed

    def _init_presentation(self) -> None:
        """Initialize Presentation Layer."""
        from iFactory.presentation.adapters.signal_bus import SignalBus
        from iFactory.presentation.di.container import UIContainer

        self._signal_bus = SignalBus()
        self._ui_container = UIContainer(app_container=self)
        self._ui_container.initialize()

    # -------------------------------------------------------------------------
    # Public Properties
    # -------------------------------------------------------------------------

    @property
    def device_facade(self):
        """Legacy - no facade needed in remote-first architecture."""
        return None

    @property
    def remote_source(self):
        """Get remote data source."""
        return self._remote_data_source

    @property
    def sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        """Get sync orchestrator for coordinated sync operations."""
        return self._sync_orchestrator

    @property
    def uow_factory(self) -> Optional[Callable]:
        """Get UoW factory for local persistence operations."""
        return self._uow_factory

    @property
    def db_config(self) -> Optional[DatabaseConfig]:
        """Get database configuration."""
        return self._db_config

    def get_ui_container(self) -> Optional["UIContainer"]:
        """Get UI container."""
        return self._ui_container

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def dispose(self) -> None:
        """Dispose all resources."""
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

        self._sync_orchestrator = None
        self._uow_factory = None
        self._initialized = False

        logger.info("[AppContainer] Disposed")

    # Alias for compatibility
    cleanup = dispose


__all__ = ["AppContainer"]
