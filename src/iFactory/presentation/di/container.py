# File: presentation/di/container.py
"""
UI Dependency Injection Container.

Manages all presentation layer components with proper MVVM architecture.
Uses ViewModels instead of Controllers/Presenters.

Features:
- Auto-refresh every 3 seconds for latest status
- Initial history sync on startup
- Proper shutdown handling
- Proper ViewModel dependency injection
- Centralized ThemeService management
- Icon preloading for faster startup
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QTimer

from ..constants.timing import Timing
from ..resources.icons import Icons, DeviceIcons
from ..services.page_device_manager import PageDeviceManager
from ..services.theme_service import ThemeService, get_theme_service
from ..state.reducers import INITIAL_STATE
from ..state.store import Store
from ..viewmodels import (
    DeviceListViewModel,
    GanttChartViewModel,
    ShellViewModel,
)
from ..views.main_window import MainWindow

if TYPE_CHECKING:
    from iFactory.shared.di.app_container import AppContainer
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator

logger = logging.getLogger(__name__)

AUTO_REFRESH_INTERVAL_MS = 3000


class UIContainer(QObject):
    """
    UI Container managing all presentation components.

    Architecture:
    - Uses MVVM pattern with reactive signals
    - ViewModels own UI state and orchestrate Use Cases
    - Views bind to ViewModel signals (passive consumers)
    - Redux Store for cross-cutting state (theme, selection)
    - Proper dependency injection between ViewModels
    - Centralized ThemeService for all theming needs
    - Centralized icon management with caching
    """

    def __init__(self, app_container: "AppContainer"):
        super().__init__()
        self._app = app_container
        self._is_initialized = False
        self._initial_load_done = False
        self._is_shutting_down = False

        # Core components
        self._store: Optional[Store] = None
        self._page_manager: Optional[PageDeviceManager] = None
        self._theme_service: Optional[ThemeService] = None
        self._main_window: Optional[MainWindow] = None

        # ViewModels
        self._shell_vm: Optional[ShellViewModel] = None
        self._device_vm: Optional[DeviceListViewModel] = None
        self._gantt_vm: Optional[GanttChartViewModel] = None

        # Application Layer services
        self._sync_orchestrator: Optional["SyncOrchestrator"] = None

        # Timers
        self._refresh_timer: Optional[QTimer] = None

    def initialize(self) -> None:
        """Initialize all UI components."""
        if self._is_initialized:
            return

        logger.info("[UIContainer] Initializing with MVVM architecture...")

        # Initialize ThemeService FIRST - it's needed by ViewModels and Views
        self._init_theme_service()

        # Preload commonly used icons
        self._preload_icons()

        self._init_store()
        self._init_page_manager()
        self._init_sync_orchestrator()
        self._init_viewmodels()
        self._wire_viewmodel_dependencies()
        self._init_main_window()
        self._connect_signals()
        self._init_auto_refresh()

        self._is_initialized = True
        logger.info("[UIContainer] Initialized successfully")

    def _init_theme_service(self) -> None:
        """Initialize the centralized theme service."""
        self._theme_service = get_theme_service()
        logger.info("[UIContainer] ThemeService initialized")

    def _preload_icons(self) -> None:
        """Preload commonly used icons for faster startup."""
        if not self._theme_service:
            return

        # Preload navigation icons
        nav_icons = [
            Icons.DASHBOARD,
            Icons.ORDERS,
            Icons.SETTINGS,
            Icons.LEFT_PANEL_OPEN,
            Icons.LEFT_PANEL_CLOSE,
            Icons.LOGO,
            Icons.DASHBOARD_LAYOUT,
            Icons.ORDERS_LAYOUT,
        ]

        self._theme_service.preload_icons(nav_icons)
        logger.info(f"[UIContainer] Preloaded {len(nav_icons)} navigation icons")

    def _init_store(self) -> None:
        """Initialize Redux-like store for cross-cutting state."""
        self._store = Store(INITIAL_STATE)

    def _init_page_manager(self) -> None:
        """Initialize page device manager."""
        config_path = None
        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            config_path = PATHS.device_positions_path
        except ImportError:
            pass

        self._page_manager = PageDeviceManager(config_path=config_path)
        all_devices = self._page_manager.get_all_devices()
        logger.info(f"[UIContainer] PageDeviceManager: {len(all_devices)} devices")

        # Preload device icons based on available devices
        self._preload_device_icons()

    def _preload_device_icons(self) -> None:
        """Preload device icons based on page manager devices."""
        if not self._theme_service or not self._page_manager:
            return

        try:
            # Get all device IDs from page manager
            all_devices = self._page_manager.get_all_devices()

            # Extract equipment codes (first 3 characters typically)
            device_codes = set()
            for device_id in all_devices:
                # Extract base code (e.g., "AMX" from "AMX01")
                if len(device_id) >= 3:
                    base_code = "".join(c for c in device_id[:3] if c.isalpha())
                    if base_code:
                        device_codes.add(base_code.upper())

            # Filter to valid device icons that exist in DeviceIcons enum
            device_icons = []
            for code in device_codes:
                device_icon = DeviceIcons.from_code(code)
                if device_icon:
                    device_icons.append(device_icon)

            if device_icons:
                self._theme_service.preload_icons(device_icons)
                logger.info(f"[UIContainer] Preloaded {len(device_icons)} device icons")

        except Exception as e:
            logger.warning(f"[UIContainer] Failed to preload device icons: {e}")

    def _init_sync_orchestrator(self) -> None:
        """Get or create SyncOrchestrator from Application Layer."""
        try:
            if hasattr(self._app, "sync_orchestrator") and self._app.sync_orchestrator:
                self._sync_orchestrator = self._app.sync_orchestrator
                logger.info("[UIContainer] Using SyncOrchestrator from AppContainer")
                return

            remote_source = getattr(self._app, "remote_source", None)
            uow_factory = getattr(self._app, "uow_factory", None)

            if remote_source:
                from iFactory.application.services.sync_orchestrator import create_sync_orchestrator

                self._sync_orchestrator = create_sync_orchestrator(
                    remote_source=remote_source,
                    uow_factory=uow_factory or self._create_null_uow_factory(),
                )
                logger.info("[UIContainer] Created local SyncOrchestrator")
            else:
                logger.warning("[UIContainer] No remote source - SyncOrchestrator disabled")

        except Exception as e:
            logger.error(f"[UIContainer] Failed to init SyncOrchestrator: {e}")
            self._sync_orchestrator = None

    def _create_null_uow_factory(self):
        """Create no-op UoW factory when no local database is available."""
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

    def _init_viewmodels(self) -> None:
        """Initialize all ViewModels with proper dependencies."""
        config_path = None
        mssql_url = None
        remote_source = None

        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            config_path = PATHS.device_positions_path
        except ImportError:
            pass

        try:
            if hasattr(self._app, "db_config") and self._app.db_config:
                mssql_url = self._app.db_config.mssql_url

            if hasattr(self._app, "remote_source") and self._app.remote_source:
                remote_source = self._app.remote_source
        except Exception as e:
            logger.warning(f"[UIContainer] Could not get remote config: {e}")

        # 1. Shell ViewModel - inject ThemeService
        self._shell_vm = ShellViewModel(
            theme_service=self._theme_service,
            config_path=config_path,
            page_manager=self._page_manager,
        )
        self._shell_vm.initialize()

        # 2. Device List ViewModel (will need shell_vm later)
        self._device_vm = DeviceListViewModel(
            page_manager=self._page_manager,
            remote_source=remote_source,
            sync_orchestrator=self._sync_orchestrator,
            shell_vm=None,  # Set later in _wire_viewmodel_dependencies
        )
        self._device_vm.initialize()

        # 3. Gantt Chart ViewModel
        self._gantt_vm = GanttChartViewModel(mssql_url=mssql_url)
        self._gantt_vm.initialize()

        logger.info("[UIContainer] ViewModels initialized")

    def _wire_viewmodel_dependencies(self) -> None:
        """Wire up cross-ViewModel dependencies after initial creation."""
        if self._device_vm and self._shell_vm:
            self._device_vm.set_shell_viewmodel(self._shell_vm)
            logger.info("[UIContainer] Wired DeviceVM -> ShellVM")

    def _init_main_window(self) -> None:
        """Initialize main window with ViewModels and ThemeService."""
        self._main_window = MainWindow(
            store=self._store,
            shell_vm=self._shell_vm,
            device_vm=self._device_vm,
            gantt_vm=self._gantt_vm,
            theme_service=self._theme_service,
            page_manager=self._page_manager,
        )

    def _connect_signals(self) -> None:
        """Connect ViewModel signals to Store for cross-cutting state."""
        if self._device_vm and self._store:
            self._device_vm.devicesChanged.connect(self._on_devices_changed)
            self._device_vm.selectionChanged.connect(self._on_selection_changed)
            self._device_vm.syncStatusChanged.connect(self._on_sync_status_changed)

        if self._shell_vm and self._store:
            self._shell_vm.themeChanged.connect(self._on_theme_changed)
            self._shell_vm.pageChanged.connect(self._on_page_changed)
            self._shell_vm.sidebarChanged.connect(self._on_sidebar_changed)
            self._shell_vm.rightPanelChanged.connect(self._on_right_panel_changed)

        if self._gantt_vm:
            self._gantt_vm.chartReady.connect(self._on_chart_ready)

    def _init_auto_refresh(self) -> None:
        """Initialize auto-refresh timer for latest status."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(AUTO_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._on_auto_refresh)
        logger.info(f"[UIContainer] Auto-refresh: {AUTO_REFRESH_INTERVAL_MS}ms")

    # =========================================================================
    # Signal Handlers (ViewModel -> Store sync)
    # =========================================================================

    def _on_devices_changed(self, devices: dict) -> None:
        from ..state.actions import load_devices

        self._store.dispatch(load_devices(devices))

    def _on_selection_changed(self, selection) -> None:
        from ..state.actions import select_device_only, deselect_device

        if selection.has_selection:
            self._store.dispatch(select_device_only(selection.selected_device_id))
        else:
            self._store.dispatch(deselect_device())

    def _on_sync_status_changed(self, status) -> None:
        from ..state.actions import update_system_status, set_loading

        self._store.dispatch(set_loading(status.is_syncing))

        if status.has_error:
            self._store.dispatch(update_system_status(mssql=False, sqlite=True, message=status.error_message))
        elif status.last_sync_time:
            self._store.dispatch(
                update_system_status(mssql=True, sqlite=True, message=f"Synced {status.synced_count} devices @ {status.last_sync_time}")
            )

    def _on_theme_changed(self, theme: str) -> None:
        from ..state.actions import set_theme

        self._store.dispatch(set_theme(theme))

    def _on_page_changed(self, page: str) -> None:
        from ..state.actions import set_page

        self._store.dispatch(set_page(page))

    def _on_sidebar_changed(self, expanded: bool) -> None:
        state = self._store.get_state()
        if state.get("sidebar_expanded") != expanded:
            from ..state.actions import toggle_sidebar

            self._store.dispatch(toggle_sidebar())

    def _on_right_panel_changed(self, expanded: bool) -> None:
        """Sync right panel state to store."""
        state = self._store.get_state()
        current_expanded = state.get("right_panel_expanded", False)

        if current_expanded != expanded:
            from ..state.actions import toggle_right_panel

            self._store.dispatch(toggle_right_panel())
            logger.debug(f"[UIContainer] Store right_panel_expanded -> {expanded}")

    def _on_chart_ready(self, chart) -> None:
        from ..state.actions import set_selected_device_gantt

        self._store.dispatch(set_selected_device_gantt(chart))

    def _on_auto_refresh(self) -> None:
        if self._is_shutting_down:
            return
        if self._device_vm:
            self._device_vm.load_devices()

    # =========================================================================
    # Public API
    # =========================================================================

    def schedule_deferred_data_load(self) -> None:
        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._start_data_loading)

    def _start_data_loading(self) -> None:
        if self._initial_load_done:
            return
        self._initial_load_done = True
        logger.info("[UIContainer] Starting initial data load...")

        if self._device_vm:
            self._device_vm.load_devices()

        if self._refresh_timer:
            self._refresh_timer.start()
            logger.info("[UIContainer] Auto-refresh timer started")

    def get_main_window(self) -> Optional[MainWindow]:
        return self._main_window

    def get_device_viewmodel(self) -> Optional[DeviceListViewModel]:
        return self._device_vm

    def get_gantt_viewmodel(self) -> Optional[GanttChartViewModel]:
        return self._gantt_vm

    def get_shell_viewmodel(self) -> Optional[ShellViewModel]:
        return self._shell_vm

    def get_page_manager(self) -> Optional[PageDeviceManager]:
        return self._page_manager

    def get_store(self) -> Optional[Store]:
        return self._store

    def get_theme_service(self) -> Optional[ThemeService]:
        """Get the centralized theme service."""
        return self._theme_service

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def shutdown(self) -> None:
        if not self._is_initialized:
            return

        self._is_shutting_down = True
        logger.info("[UIContainer] Shutting down...")

        if self._refresh_timer:
            self._refresh_timer.stop()
            self._refresh_timer.deleteLater()
            self._refresh_timer = None

        if self._device_vm:
            self._device_vm.dispose()

        if self._gantt_vm:
            self._gantt_vm.dispose()

        if self._shell_vm:
            self._shell_vm.dispose()

        if self._main_window:
            self._main_window.close()

        self._is_initialized = False
        logger.info("[UIContainer] Shutdown complete")


__all__ = ["UIContainer"]
