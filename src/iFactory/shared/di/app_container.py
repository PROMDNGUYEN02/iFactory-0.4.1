# src/iFactory/shared/di/app_container.py
"""
Main Application DI Container - Enhanced with dependency-injector.

Uses the dependency-injector library for professional DI management:
- Lazy initialization
- Proper lifecycle management
- Wiring for automatic injection
- Configuration overrides for testing
"""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from dependency_injector import containers, providers

from iFactory.infrastructure.configuration.paths import PATHS
from iFactory.infrastructure.configuration.db_settings import DatabaseConfig
from iFactory.infrastructure.configuration.settings import SettingsManager

if TYPE_CHECKING:
    from iFactory.application.ports.uow import AbstractUnitOfWork
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator
    from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter
    from iFactory.infrastructure.adapters.mssql_adapter import MssqlAdapter
    from iFactory.infrastructure.persistence.sqlalchemy.database import DatabaseManager
    from iFactory.presentation.di.container import UIContainer

logger = logging.getLogger(__name__)


# ============================================================================
# Factory Functions
# ============================================================================


def _create_device_adapter() -> Optional["DeviceFileAdapter"]:
    """Factory for DeviceFileAdapter."""
    try:
        from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter

        adapter = DeviceFileAdapter()

        mapping = adapter.get_display_to_remote_mapping()
        mapped_count = sum(1 for k, v in mapping.items() if k != v)

        if mapped_count:
            logger.info(f"DeviceFileAdapter: {mapped_count} ID mappings configured")

        return adapter
    except Exception as e:
        logger.warning(f"DeviceFileAdapter creation failed: {e}")
        return None


def _create_remote_source(db_config: DatabaseConfig) -> Optional["MssqlAdapter"]:
    """Factory for remote data source."""
    if not db_config.is_mssql_configured:
        logger.info("MSSQL not configured - remote source disabled")
        return None

    try:
        from iFactory.infrastructure.adapters.mssql_adapter import MssqlAdapter

        # Use mssql_url property (handles both async and sync naming)
        url = getattr(db_config, "mssql_async_url", None) or getattr(db_config, "mssql_url", None)
        if url:
            return MssqlAdapter(url)
        return None
    except Exception as e:
        logger.error(f"Remote data source creation failed: {e}")
        return None


def _create_db_manager(db_config: DatabaseConfig) -> Optional["DatabaseManager"]:
    """Factory for database manager."""
    try:
        from iFactory.infrastructure.persistence.sqlalchemy.database import DatabaseManager

        return DatabaseManager(db_config.storage_db_url)
    except Exception as e:
        logger.error(f"Database manager creation failed: {e}")
        return None


def _create_null_uow_factory() -> Callable[[], "AbstractUnitOfWork"]:
    """Create no-op UoW factory."""
    from iFactory.application.ports.uow import AbstractUnitOfWork

    class NullUnitOfWork(AbstractUnitOfWork):
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


# ============================================================================
# Infrastructure Container (dependency-injector)
# ============================================================================


class InfrastructureContainer(containers.DeclarativeContainer):
    """Container for infrastructure components."""

    config = providers.Configuration()

    # Settings
    settings_manager = providers.Singleton(SettingsManager)

    # Database configuration
    db_config = providers.Singleton(DatabaseConfig)

    # Device file adapter (ID mapping)
    device_file_adapter = providers.Singleton(_create_device_adapter)

    # Remote data source (MSSQL) - depends on db_config
    remote_data_source = providers.Singleton(
        _create_remote_source,
        db_config,
    )

    # Database manager (SQLite) - depends on db_config
    database_manager = providers.Singleton(
        _create_db_manager,
        db_config,
    )


# ============================================================================
# Main Application Container (Facade Pattern)
# ============================================================================


class AppContainer:
    """
    Main Application Container - Facade over dependency-injector containers.

    This class provides the same interface as the old AppContainer while
    using dependency-injector internally for infrastructure management.

    Usage:
        container = AppContainer()
        await container.initialize()

        # Access components
        settings = container.settings
        sync_orch = container.sync_orchestrator

        # Cleanup
        await container.dispose()
    """

    __slots__ = (
        "_base_dir",
        "_infrastructure",
        "_sync_orchestrator",
        "_ui_container",
        "_uow_factory",
        "_initialized",
    )

    def __init__(self, base_dir: Optional[Path] = None) -> None:
        self._base_dir = base_dir or PATHS.project_root
        self._infrastructure = InfrastructureContainer()
        self._sync_orchestrator: Optional["SyncOrchestrator"] = None
        self._ui_container: Optional["UIContainer"] = None
        self._uow_factory: Optional[Callable[[], "AbstractUnitOfWork"]] = None
        self._initialized = False

        # Configure infrastructure
        self._infrastructure.config.from_dict(
            {
                "base_dir": str(self._base_dir),
                "debug": False,
            }
        )

    async def initialize(self) -> None:
        """Initialize all container components."""
        if self._initialized:
            return

        logger.info("[AppContainer] Initializing with dependency-injector...")

        # Ensure directories exist
        PATHS.ensure_directories()

        # Initialize database manager (async)
        db_manager = self._infrastructure.database_manager()
        if db_manager:
            await db_manager.initialize()
            logger.info("[AppContainer] Database manager initialized")

        # Create UoW factory
        self._init_uow_factory()

        # Create sync orchestrator
        self._init_sync_orchestrator()

        # Initialize presentation layer
        self._init_presentation()

        self._initialized = True
        logger.info("[AppContainer] Initialization complete")

    def _init_uow_factory(self) -> None:
        """Initialize Unit of Work factory."""
        db_manager = self._infrastructure.database_manager()

        if db_manager and db_manager.session_factory:
            try:
                from iFactory.infrastructure.persistence.sqlalchemy import SqlAlchemyUnitOfWork

                self._uow_factory = lambda: SqlAlchemyUnitOfWork(db_manager.session_factory)
                logger.info("[AppContainer] UoW factory configured")
            except ImportError as e:
                logger.warning(f"UoW factory import failed: {e}")
                self._uow_factory = _create_null_uow_factory()
        else:
            self._uow_factory = _create_null_uow_factory()
            logger.info("[AppContainer] Using null UoW factory")

    def _init_sync_orchestrator(self) -> None:
        """Initialize sync orchestrator."""
        remote_source = self._infrastructure.remote_data_source()

        if not remote_source:
            logger.warning("[AppContainer] No remote source - sync orchestrator disabled")
            return

        try:
            from iFactory.application.services.sync_orchestrator import create_sync_orchestrator

            self._sync_orchestrator = create_sync_orchestrator(
                remote_source=remote_source,
                uow_factory=self._uow_factory or _create_null_uow_factory(),
                id_mapper=self._infrastructure.device_file_adapter(),
                on_sync_complete=self._on_sync_complete,
            )
            logger.info("[AppContainer] SyncOrchestrator configured")

        except Exception as e:
            logger.error(f"SyncOrchestrator init failed: {e}")
            self._sync_orchestrator = None

    def _on_sync_complete(self, result: Any) -> None:
        """Handle sync completion."""
        logger.debug(f"[AppContainer] Sync completed: {getattr(result, 'count', 0)} devices")

    def _init_presentation(self) -> None:
        """Initialize presentation layer."""
        try:
            from iFactory.presentation.di.container import UIContainer

            # UIContainer expects an object with specific properties
            self._ui_container = UIContainer(app_container=self)
            self._ui_container.initialize()
            logger.info("[AppContainer] UI container initialized")

        except Exception as e:
            logger.error(f"Presentation init failed: {e}")
            self._ui_container = None

    # ========================================================================
    # Public Properties (Interface for other components)
    # ========================================================================

    @property
    def remote_source(self) -> Optional["MssqlAdapter"]:
        """Get remote data source."""
        return self._infrastructure.remote_data_source()

    @property
    def device_file_adapter(self) -> Optional["DeviceFileAdapter"]:
        """Get device file adapter."""
        return self._infrastructure.device_file_adapter()

    @property
    def id_mapper(self) -> Optional["DeviceFileAdapter"]:
        """Get ID mapper (alias for device_file_adapter)."""
        return self.device_file_adapter

    @property
    def sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        """Get sync orchestrator."""
        return self._sync_orchestrator

    @property
    def uow_factory(self) -> Optional[Callable[[], "AbstractUnitOfWork"]]:
        """Get UoW factory."""
        return self._uow_factory

    @property
    def db_config(self) -> DatabaseConfig:
        """Get database configuration."""
        return self._infrastructure.db_config()

    @property
    def db_manager(self) -> Optional["DatabaseManager"]:
        """Get database manager."""
        return self._infrastructure.database_manager()

    @property
    def settings(self) -> SettingsManager:
        """Get settings manager."""
        return self._infrastructure.settings_manager()

    def get_ui_container(self) -> Optional["UIContainer"]:
        """Get UI container."""
        return self._ui_container

    # ========================================================================
    # Lifecycle
    # ========================================================================

    async def dispose(self) -> None:
        """Dispose all resources."""
        logger.info("[AppContainer] Disposing...")

        # Shutdown UI first
        if self._ui_container:
            try:
                self._ui_container.shutdown()
            except Exception as e:
                logger.warning(f"UI shutdown error: {e}")
            self._ui_container = None

        # Brief delay for pending operations
        await asyncio.sleep(0.1)

        # Dispose remote source
        remote = self._infrastructure.remote_data_source()
        if remote:
            try:
                if hasattr(remote, "cancel_pending"):
                    await remote.cancel_pending()
                await remote.dispose()
            except Exception as e:
                logger.warning(f"Remote source dispose error: {e}")

        # Dispose database manager
        db_manager = self._infrastructure.database_manager()
        if db_manager:
            try:
                await db_manager.dispose()
            except Exception as e:
                logger.warning(f"Database manager dispose error: {e}")

        # Clear device adapter cache
        adapter = self._infrastructure.device_file_adapter()
        if adapter and hasattr(adapter, "invalidate_cache"):
            adapter.invalidate_cache()

        # Reset container singletons
        self._infrastructure.reset_singletons()

        self._sync_orchestrator = None
        self._uow_factory = None
        self._initialized = False

        logger.info("[AppContainer] Disposed")

    # Alias for backward compatibility
    cleanup = dispose


__all__ = [
    "AppContainer",
    "InfrastructureContainer",
]
