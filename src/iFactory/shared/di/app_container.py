"""
Main Application DI Container - Remote-First Architecture with MVVM.

Wires up Application Layer components (SyncOrchestrator, Handlers) and
provides them to the Presentation Layer using MVVM pattern.
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
    from iFactory.infrastructure.persistence.sqlalchemy.database import DatabaseManager

logger = logging.getLogger(__name__)


class AppContainer:
    """
    Main Application Container.

    Responsibilities:
    - Initialize infrastructure components (remote source, databases)
    - Create Application Layer services (SyncOrchestrator)
    - Provide dependencies to Presentation Layer (ViewModels)

    Architecture:
    - Remote-First: Device status fetched directly from MSSQL
    - MVVM Pattern: ViewModels orchestrate Use Cases
    - New Sync API: SyncOrchestrator receives explicit device IDs
    """

    __slots__ = (
        "_base_dir",
        "_settings",
        "_db_config",
        "_db_manager",
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
        self._db_manager: Optional["DatabaseManager"] = None
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

        logger.info("[AppContainer] Initializing with MVVM architecture...")

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

        # Initialize UoW factory for history caching
        await self._init_uow_factory()

    async def _init_uow_factory(self) -> None:
        """Initialize Unit of Work factory for local caching."""
        try:
            from iFactory.infrastructure.persistence.sqlalchemy import (
                DatabaseManager,
                SqlAlchemyUnitOfWork,
            )

            sqlite_url = None
            if self._db_config:
                sqlite_url = getattr(self._db_config, "storage_db_url", None)
                if not sqlite_url:
                    sqlite_url = getattr(self._db_config, "sqlite_url", None)

            if sqlite_url:
                self._db_manager = DatabaseManager(sqlite_url)
                await self._db_manager.initialize()

                session_factory = self._db_manager.session_factory
                self._uow_factory = lambda: SqlAlchemyUnitOfWork(session_factory)

                logger.info("[AppContainer] UoW factory configured for history caching")
            else:
                self._uow_factory = None
                logger.info("[AppContainer] No local database URL - history caching disabled")

        except ImportError as e:
            logger.warning(f"UoW factory init failed (import error): {e}")
            self._uow_factory = None
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

    def _init_presentation(self) -> None:
        """Initialize Presentation Layer with MVVM architecture."""
        from iFactory.presentation.adapters.signal_bus import SignalBus
        from iFactory.presentation.di.container import UIContainer

        self._signal_bus = SignalBus()
        self._ui_container = UIContainer(app_container=self)
        self._ui_container.initialize()

    # -------------------------------------------------------------------------
    # Public Properties
    # -------------------------------------------------------------------------

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

    @property
    def db_manager(self) -> Optional["DatabaseManager"]:
        """Get database manager."""
        return self._db_manager

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

        # Wait a bit for pending operations to complete
        import asyncio

        await asyncio.sleep(0.2)

        # Dispose remote source with proper cleanup
        if self._remote_data_source:
            try:
                # Cancel any pending operations first
                if hasattr(self._remote_data_source, "cancel_pending"):
                    await self._remote_data_source.cancel_pending()
                await self._remote_data_source.dispose()
            except Exception as e:
                logger.warning(f"Error disposing remote source: {e}")
            finally:
                self._remote_data_source = None

        # Dispose database manager
        if self._db_manager:
            try:
                await self._db_manager.dispose()
            except Exception as e:
                logger.warning(f"Error disposing database manager: {e}")
            finally:
                self._db_manager = None

        self._sync_orchestrator = None
        self._uow_factory = None
        self._initialized = False

        logger.info("[AppContainer] Disposed")

    cleanup = dispose


__all__ = ["AppContainer"]
