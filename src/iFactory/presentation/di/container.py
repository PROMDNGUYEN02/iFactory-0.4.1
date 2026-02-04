# src/iFactory/presentation/di/container.py
"""
Refactored UI Dependency Injection Container.

Changes from original:
- Split into focused sub-containers
- Interface-based dependencies
- Lazy initialization
- Better error handling
- Cleaner lifecycle management
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional, Protocol, TypeVar

from PySide6.QtCore import QObject, QTimer

if TYPE_CHECKING:
    from iFactory.shared.di.app_container import AppContainer
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator
    from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter
    from ..services.page_device_manager import PageDeviceManager
    from ..services.theme_service import ThemeService
    from ..services.icon_service import IconService
    from ..state.store import Store
    from ..viewmodels import (
        DeviceListViewModel,
        GanttChartViewModel,
        ShellViewModel,
    )
    from ..views.main_window import MainWindow

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Configuration
# ============================================================================


@dataclass
class UIContainerConfig:
    """Configuration for UIContainer."""

    auto_refresh_interval_ms: int = 3000
    deferred_load_delay_ms: int = 100
    preload_icons: bool = True
    enable_time_travel: bool = False
    persist_state: bool = False
    state_persistence_path: Optional[str] = None


# ============================================================================
# Protocols for Dependencies
# ============================================================================


class IRemoteSource(Protocol):
    """Protocol for remote data source."""

    async def fetch_device_status(self, device_ids: list) -> dict: ...


class IUnitOfWorkFactory(Protocol):
    """Protocol for UoW factory."""

    def __call__(self) -> "AbstractUnitOfWork": ...


class IIdMapper(Protocol):
    """Protocol for ID mapping."""

    def get_remote_id(self, display_id: str) -> str: ...
    def get_display_id(self, remote_id: str) -> str: ...


# ============================================================================
# Service Locator Pattern for Lazy Init
# ============================================================================


class ServiceRegistry:
    """
    Simple service registry for lazy initialization.

    Services are created on first access.
    """

    def __init__(self):
        self._factories: dict[type, Callable] = {}
        self._instances: dict[type, object] = {}
        self._lock = None  # Thread lock if needed

    def register(self, service_type: type, factory: Callable[[], T]) -> None:
        """Register a service factory."""
        self._factories[service_type] = factory

    def get(self, service_type: type[T]) -> T:
        """Get or create service instance."""
        if service_type not in self._instances:
            if service_type not in self._factories:
                raise KeyError(f"Service {service_type} not registered")
            self._instances[service_type] = self._factories[service_type]()
        return self._instances[service_type]

    def has(self, service_type: type) -> bool:
        """Check if service is registered."""
        return service_type in self._factories

    def clear(self) -> None:
        """Clear all instances (for shutdown)."""
        self._instances.clear()


# ============================================================================
# Sub-Containers
# ============================================================================


class ServicesContainer:
    """Container for core services."""

    def __init__(self, app_container: "AppContainer"):
        self._app = app_container
        self._theme_service: Optional["ThemeService"] = None
        self._icon_service: Optional["IconService"] = None
        self._page_manager: Optional["PageDeviceManager"] = None
        self._id_mapper: Optional["DeviceFileAdapter"] = None

    @property
    def theme_service(self) -> "ThemeService":
        if self._theme_service is None:
            from ..services.theme_service import get_theme_service

            self._theme_service = get_theme_service()
            logger.debug("[Services] ThemeService initialized")
        return self._theme_service

    @property
    def icon_service(self) -> "IconService":
        if self._icon_service is None:
            from ..services.icon_service import get_icon_service

            self._icon_service = get_icon_service(self.theme_service)
            logger.debug("[Services] IconService initialized")
        return self._icon_service

    @property
    def page_manager(self) -> "PageDeviceManager":
        if self._page_manager is None:
            from ..services.page_device_manager import PageDeviceManager

            config_path = self._get_config_path()
            self._page_manager = PageDeviceManager(config_path=config_path)
            logger.debug("[Services] PageDeviceManager initialized")
        return self._page_manager

    @property
    def id_mapper(self) -> Optional["DeviceFileAdapter"]:
        if self._id_mapper is None:
            self._id_mapper = self._init_id_mapper()
        return self._id_mapper

    def _get_config_path(self) -> Optional[str]:
        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            return PATHS.device_positions_path
        except ImportError:
            return None

    def _init_id_mapper(self) -> Optional["DeviceFileAdapter"]:
        """Initialize ID mapper from AppContainer or create local."""
        try:
            # Try AppContainer first
            for attr in ("device_file_adapter", "id_mapper"):
                mapper = getattr(self._app, attr, None)
                if mapper:
                    logger.debug(f"[Services] Using ID mapper from AppContainer.{attr}")
                    return mapper

            # Create local instance
            from iFactory.infrastructure.adapters.device_file_adapter import DeviceFileAdapter

            mapper = DeviceFileAdapter()
            logger.debug("[Services] Created local DeviceFileAdapter")
            return mapper

        except Exception as e:
            logger.warning(f"[Services] Failed to init ID mapper: {e}")
            return None

    def preload_icons(self) -> int:
        """Preload commonly used icons."""
        count = self.icon_service.preload_navigation_icons()
        count += self.icon_service.preload_action_icons()

        # Preload device icons based on page manager
        try:
            all_devices = self.page_manager.get_all_devices()
            device_codes = set()
            for device_id in all_devices:
                if len(device_id) >= 3:
                    if device_id.startswith(("CA1", "CA2")):
                        device_codes.add(device_id[:3])
                    else:
                        base = "".join(c for c in device_id[:3] if c.isalpha())
                        if base:
                            device_codes.add(base.upper())
            count += self.icon_service.preload_device_icons(list(device_codes))
        except Exception as e:
            logger.warning(f"[Services] Device icon preload failed: {e}")

        return count

    def shutdown(self) -> None:
        """Cleanup services."""
        if self._icon_service:
            self._icon_service.clear_cache()


class StateContainer:
    """Container for state management."""

    def __init__(self, config: UIContainerConfig):
        self._config = config
        self._store: Optional["Store"] = None

    @property
    def store(self) -> "Store":
        if self._store is None:
            self._store = self._create_store()
        return self._store

    def _create_store(self) -> "Store":
        from ..state.store import Store, StoreConfig, LocalStoragePersistence
        from ..state.reducers import INITIAL_STATE_DICT
        from pathlib import Path

        persistence = None
        if self._config.persist_state and self._config.state_persistence_path:
            persistence = LocalStoragePersistence(Path(self._config.state_persistence_path))

        store_config = StoreConfig(
            enable_time_travel=self._config.enable_time_travel,
            persistence=persistence,
            enable_logging=True,
        )

        return Store(
            initial_state=INITIAL_STATE_DICT,
            config=store_config,
        )

    def shutdown(self) -> None:
        """Cleanup state."""
        pass  # Store doesn't need cleanup


class ViewModelsContainer:
    """Container for ViewModels."""

    def __init__(
        self,
        app_container: "AppContainer",
        services: ServicesContainer,
    ):
        self._app = app_container
        self._services = services

        self._shell_vm: Optional["ShellViewModel"] = None
        self._device_vm: Optional["DeviceListViewModel"] = None
        self._gantt_vm: Optional["GanttChartViewModel"] = None

        self._sync_orchestrator: Optional["SyncOrchestrator"] = None

        # Track if dependencies are wired
        self._dependencies_wired: bool = False

    @property
    def sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        if self._sync_orchestrator is None:
            self._sync_orchestrator = self._init_sync_orchestrator()
        return self._sync_orchestrator

    @property
    def shell_vm(self) -> "ShellViewModel":
        if self._shell_vm is None:
            self._shell_vm = self._create_shell_vm()
            # Auto-wire after creation if device_vm exists
            self._try_wire_dependencies()
        return self._shell_vm

    @property
    def device_vm(self) -> "DeviceListViewModel":
        if self._device_vm is None:
            self._device_vm = self._create_device_vm()
            # Auto-wire after creation if shell_vm exists
            self._try_wire_dependencies()
        return self._device_vm

    @property
    def gantt_vm(self) -> "GanttChartViewModel":
        if self._gantt_vm is None:
            self._gantt_vm = self._create_gantt_vm()
        return self._gantt_vm

    def _init_sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        """Get or create SyncOrchestrator."""
        try:
            # From AppContainer
            if hasattr(self._app, "sync_orchestrator") and self._app.sync_orchestrator:
                logger.debug("[ViewModels] Using SyncOrchestrator from AppContainer")
                return self._app.sync_orchestrator

            # Create local
            remote_source = getattr(self._app, "remote_source", None)
            if remote_source:
                from iFactory.application.services.sync_orchestrator import create_sync_orchestrator

                orchestrator = create_sync_orchestrator(
                    remote_source=remote_source,
                    uow_factory=getattr(self._app, "uow_factory", None) or self._null_uow_factory(),
                    id_mapper=self._services.id_mapper,
                )
                logger.debug("[ViewModels] Created local SyncOrchestrator")
                return orchestrator

            logger.warning("[ViewModels] No remote source - SyncOrchestrator disabled")
            return None

        except Exception as e:
            logger.error(f"[ViewModels] SyncOrchestrator init failed: {e}")
            return None

    def _null_uow_factory(self):
        """Create no-op UoW factory."""
        from iFactory.application.ports.uow import AbstractUnitOfWork

        class NullUoW(AbstractUnitOfWork):
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

        return lambda: NullUoW()

    def _create_shell_vm(self) -> "ShellViewModel":
        from ..viewmodels import ShellViewModel

        vm = ShellViewModel(
            theme_service=self._services.theme_service,
            config_path=self._services._get_config_path(),
            page_manager=self._services.page_manager,
        )
        vm.initialize()
        return vm

    def _create_device_vm(self) -> "DeviceListViewModel":
        from ..viewmodels import DeviceListViewModel

        remote_source = getattr(self._app, "remote_source", None)

        vm = DeviceListViewModel(
            page_manager=self._services.page_manager,
            remote_source=remote_source,
            sync_orchestrator=self.sync_orchestrator,
            shell_vm=self._shell_vm,  # Pass if already created
            id_mapper=self._services.id_mapper,
        )
        vm.initialize()
        return vm

    def _create_gantt_vm(self) -> "GanttChartViewModel":
        from ..viewmodels import GanttChartViewModel

        mssql_url = None
        if hasattr(self._app, "db_config") and self._app.db_config:
            mssql_url = self._app.db_config.mssql_url

        vm = GanttChartViewModel(
            mssql_url=mssql_url,
            id_mapper=self._services.id_mapper,
        )
        vm.initialize()
        return vm

    def _try_wire_dependencies(self) -> None:
        """Try to wire dependencies if both VMs exist."""
        if self._dependencies_wired:
            return

        if self._device_vm is not None and self._shell_vm is not None:
            # Check if already wired (shell_vm might be passed in constructor)
            if self._device_vm._shell_vm is None:
                self._device_vm.set_shell_viewmodel(self._shell_vm)
                logger.debug("[ViewModels] Auto-wired DeviceVM -> ShellVM")
            self._dependencies_wired = True

    def wire_dependencies(self) -> None:
        """
        Wire cross-ViewModel dependencies.

        NOTE: This is now mostly handled by _try_wire_dependencies()
        which is called automatically when VMs are created.
        This method is kept for explicit wiring if needed.
        """
        if self._dependencies_wired:
            return

        # Force creation of both VMs to trigger auto-wiring
        _ = self.shell_vm
        _ = self.device_vm

        # Explicit wire as fallback
        if self._device_vm and self._shell_vm:
            if self._device_vm._shell_vm is None:
                self._device_vm.set_shell_viewmodel(self._shell_vm)
                logger.debug("[ViewModels] Explicitly wired DeviceVM -> ShellVM")
            self._dependencies_wired = True

    def shutdown(self) -> None:
        """Cleanup ViewModels."""
        for vm in (self._device_vm, self._gantt_vm, self._shell_vm):
            if vm and hasattr(vm, "dispose"):
                vm.dispose()


# ============================================================================
# Main UIContainer
# ============================================================================


class UIContainer(QObject):
    """
    Main UI Container - Facade for all presentation layer components.

    Uses sub-containers for organization:
    - ServicesContainer: Core services (theme, icons, etc.)
    - StateContainer: Redux store
    - ViewModelsContainer: MVVM ViewModels
    """

    def __init__(
        self,
        app_container: "AppContainer",
        config: Optional[UIContainerConfig] = None,
    ):
        super().__init__()

        self._app = app_container
        self._config = config or UIContainerConfig()

        # State flags
        self._is_initialized = False
        self._initial_load_done = False
        self._is_shutting_down = False

        # Sub-containers (lazy init)
        self._services: Optional[ServicesContainer] = None
        self._state: Optional[StateContainer] = None
        self._viewmodels: Optional[ViewModelsContainer] = None

        # Main window
        self._main_window: Optional["MainWindow"] = None

        # Timers
        self._refresh_timer: Optional[QTimer] = None

    # ========================================================================
    # Initialization
    # ========================================================================

    def initialize(self) -> None:
        """Initialize all UI components."""
        if self._is_initialized:
            return

        logger.info("[UIContainer] Initializing...")

        try:
            # 1. Services
            self._services = ServicesContainer(self._app)
            if self._config.preload_icons:
                count = self._services.preload_icons()
                logger.info(f"[UIContainer] Preloaded {count} icons")

            # 2. State
            self._state = StateContainer(self._config)

            # 3. ViewModels
            self._viewmodels = ViewModelsContainer(self._app, self._services)
            # NOTE: Don't call wire_dependencies() here yet - VMs are lazy!

            # 4. Main Window - This triggers VM creation
            self._init_main_window()

            # 5. Wire dependencies AFTER VMs are created by MainWindow
            self._viewmodels.wire_dependencies()

            # 6. Connect signals
            self._connect_signals()

            # 7. Auto-refresh timer
            self._init_auto_refresh()

            self._is_initialized = True
            logger.info("[UIContainer] Initialized successfully")

        except Exception as e:
            logger.error(f"[UIContainer] Initialization failed: {e}")
            raise

    def _init_main_window(self) -> None:
        """Initialize main window."""
        from ..views.main_window import MainWindow

        self._main_window = MainWindow(
            store=self._state.store,
            shell_vm=self._viewmodels.shell_vm,
            device_vm=self._viewmodels.device_vm,
            gantt_vm=self._viewmodels.gantt_vm,
            theme_service=self._services.theme_service,
            page_manager=self._services.page_manager,
        )

    def _connect_signals(self) -> None:
        """Connect ViewModel signals to Store."""
        store = self._state.store
        device_vm = self._viewmodels.device_vm
        shell_vm = self._viewmodels.shell_vm
        gantt_vm = self._viewmodels.gantt_vm

        # Device signals
        if device_vm:
            device_vm.devicesChanged.connect(self._on_devices_changed)
            device_vm.selectionChanged.connect(self._on_selection_changed)
            device_vm.syncStatusChanged.connect(self._on_sync_status_changed)

        # Shell signals
        if shell_vm:
            shell_vm.themeChanged.connect(self._on_theme_changed)
            shell_vm.pageChanged.connect(self._on_page_changed)
            shell_vm.sidebarChanged.connect(self._on_sidebar_changed)
            shell_vm.rightPanelChanged.connect(self._on_right_panel_changed)

        # Gantt signals
        if gantt_vm:
            gantt_vm.chartReady.connect(self._on_chart_ready)

    def _init_auto_refresh(self) -> None:
        """Initialize auto-refresh timer."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(self._config.auto_refresh_interval_ms)
        self._refresh_timer.timeout.connect(self._on_auto_refresh)
        logger.debug(f"[UIContainer] Auto-refresh: {self._config.auto_refresh_interval_ms}ms")

    # ========================================================================
    # Signal Handlers
    # ========================================================================

    def _on_devices_changed(self, devices: dict) -> None:
        from ..state.actions import load_devices

        self._state.store.dispatch(load_devices(devices))

    def _on_selection_changed(self, selection) -> None:
        from ..state.actions import select_device_only, deselect_device

        if selection.has_selection:
            self._state.store.dispatch(select_device_only(selection.selected_device_id))
        else:
            self._state.store.dispatch(deselect_device())

    def _on_sync_status_changed(self, status) -> None:
        from ..state.actions import update_system_status, set_loading

        self._state.store.dispatch(set_loading(status.is_syncing))

        if status.has_error:
            self._state.store.dispatch(update_system_status(mssql=False, sqlite=True, message=status.error_message))
        elif status.last_sync_time:
            self._state.store.dispatch(
                update_system_status(
                    mssql=True,
                    sqlite=True,
                    message=f"Synced {status.synced_count} devices @ {status.last_sync_time}",
                )
            )

    def _on_theme_changed(self, theme: str) -> None:
        from ..state.actions import set_theme

        self._state.store.dispatch(set_theme(theme))

    def _on_page_changed(self, page: str) -> None:
        from ..state.actions import set_page

        self._state.store.dispatch(set_page(page))

    def _on_sidebar_changed(self, expanded: bool) -> None:
        state = self._state.store.get_state()
        if state.get("sidebar_expanded") != expanded:
            from ..state.actions import toggle_sidebar

            self._state.store.dispatch(toggle_sidebar())

    def _on_right_panel_changed(self, expanded: bool) -> None:
        state = self._state.store.get_state()
        if state.get("right_panel_expanded") != expanded:
            from ..state.actions import toggle_right_panel

            self._state.store.dispatch(toggle_right_panel())

    def _on_chart_ready(self, chart) -> None:
        from ..state.actions import set_selected_device_gantt

        self._state.store.dispatch(set_selected_device_gantt(chart))

    def _on_auto_refresh(self) -> None:
        if self._is_shutting_down:
            return
        if self._viewmodels and self._viewmodels._device_vm:
            self._viewmodels.device_vm.load_devices()

    # ========================================================================
    # Public API
    # ========================================================================

    def schedule_deferred_data_load(self) -> None:
        """Schedule deferred data loading after window shown."""
        QTimer.singleShot(
            self._config.deferred_load_delay_ms,
            self._start_data_loading,
        )

    def _start_data_loading(self) -> None:
        """Start initial data loading."""
        if self._initial_load_done:
            return

        self._initial_load_done = True
        logger.info("[UIContainer] Starting initial data load...")

        # Trigger initial page load
        if self._services and self._services._page_manager:
            self._services.page_manager.force_load_current_page()

        # Start auto-refresh
        if self._refresh_timer:
            self._refresh_timer.start()
            logger.info("[UIContainer] Auto-refresh started")

    # Getters
    def get_main_window(self) -> Optional["MainWindow"]:
        return self._main_window

    def get_device_viewmodel(self) -> Optional["DeviceListViewModel"]:
        return self._viewmodels.device_vm if self._viewmodels else None

    def get_gantt_viewmodel(self) -> Optional["GanttChartViewModel"]:
        return self._viewmodels.gantt_vm if self._viewmodels else None

    def get_shell_viewmodel(self) -> Optional["ShellViewModel"]:
        return self._viewmodels.shell_vm if self._viewmodels else None

    def get_page_manager(self) -> Optional["PageDeviceManager"]:
        return self._services.page_manager if self._services else None

    def get_store(self) -> Optional["Store"]:
        return self._state.store if self._state else None

    def get_theme_service(self) -> Optional["ThemeService"]:
        return self._services.theme_service if self._services else None

    def get_icon_service(self) -> Optional["IconService"]:
        return self._services.icon_service if self._services else None

    def get_id_mapper(self) -> Optional["DeviceFileAdapter"]:
        return self._services.id_mapper if self._services else None

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def shutdown(self) -> None:
        """Shutdown all components."""
        if not self._is_initialized:
            return

        self._is_shutting_down = True
        logger.info("[UIContainer] Shutting down...")

        # Stop timer
        if self._refresh_timer:
            self._refresh_timer.stop()
            self._refresh_timer.deleteLater()
            self._refresh_timer = None

        # Shutdown sub-containers
        if self._viewmodels:
            self._viewmodels.shutdown()

        if self._services:
            self._services.shutdown()

        if self._state:
            self._state.shutdown()

        # Close window
        if self._main_window:
            self._main_window.close()

        self._is_initialized = False
        logger.info("[UIContainer] Shutdown complete")


__all__ = [
    "UIContainer",
    "UIContainerConfig",
    "ServicesContainer",
    "StateContainer",
    "ViewModelsContainer",
    "ServiceRegistry",
]
