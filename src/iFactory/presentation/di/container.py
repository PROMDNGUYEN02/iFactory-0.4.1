# File: presentation/di/container.py
"""
UI Dependency Injection Container.

Manages all presentation layer components with proper dependency injection.
Uses the new Application Layer Sync API with explicit device IDs.

Features:
- Auto-refresh every 3 seconds for latest status
- Initial history sync on startup
- Incremental history sync during auto-refresh
- Proper shutdown handling
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QTimer

from ..constants.timing import Timing
from ..controllers.device_controller import DeviceController
from ..controllers.gantt_controller import GanttController
from ..controllers.shell_controller import ShellController
from ..presenters.device_presenter import DevicePresenter
from ..presenters.gantt_presenter import GanttPresenter
from ..services.page_device_manager import PageDeviceManager
from ..state.reducers import INITIAL_STATE
from ..state.store import Store
from ..views.main_window import MainWindow

if TYPE_CHECKING:
    from iFactory.shared.di.app_container import AppContainer
    from iFactory.application.services.sync_orchestrator import SyncOrchestrator

logger = logging.getLogger(__name__)

# Auto-refresh interval (3 seconds)
AUTO_REFRESH_INTERVAL_MS = 3000


class UIContainer(QObject):
    """
    UI Container managing all presentation components.

    Responsibilities:
    - Initialize and wire up all UI components
    - Manage component lifecycle
    - Coordinate sync operations via SyncOrchestrator
    - Handle auto-refresh timing

    Architecture:
    - Uses SyncOrchestrator from Application Layer
    - Passes explicit device IDs (no UI leakage to Application Layer)
    - PageDeviceManager determines which devices are relevant
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
        self._main_window: Optional[MainWindow] = None

        # Controllers
        self._shell_controller: Optional[ShellController] = None
        self._device_controller: Optional[DeviceController] = None
        self._gantt_controller: Optional[GanttController] = None

        # Application Layer services
        self._sync_orchestrator: Optional["SyncOrchestrator"] = None

        # Timers
        self._refresh_timer: Optional[QTimer] = None
        self._history_sync_timer: Optional[QTimer] = None

    def initialize(self) -> None:
        """Initialize all UI components."""
        if self._is_initialized:
            return

        logger.info("[UIContainer] Initializing...")

        self._init_store()
        self._init_page_manager()
        self._init_sync_orchestrator()
        self._init_controllers()
        self._init_main_window()
        self._connect_signals()
        self._wire_gantt_to_window()
        self._init_auto_refresh()

        self._is_initialized = True
        logger.info("[UIContainer] Initialized successfully")

    def _init_store(self) -> None:
        """Initialize Redux-like store."""
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
        logger.info(f"[UIContainer] PageDeviceManager initialized with " f"{len(all_devices)} devices")

    def _init_sync_orchestrator(self) -> None:
        """Get or create SyncOrchestrator from Application Layer."""
        try:
            # Get from app container if available
            if hasattr(self._app, "sync_orchestrator") and self._app.sync_orchestrator:
                self._sync_orchestrator = self._app.sync_orchestrator
                logger.info("[UIContainer] Using SyncOrchestrator from AppContainer")
                return

            # Create locally if app container doesn't provide one
            remote_source = getattr(self._app, "remote_source", None)
            uow_factory = getattr(self._app, "uow_factory", None)

            if remote_source:
                from iFactory.application.services.sync_orchestrator import (
                    create_sync_orchestrator,
                )

                self._sync_orchestrator = create_sync_orchestrator(
                    remote_source=remote_source,
                    uow_factory=uow_factory or self._create_null_uow_factory(),
                    on_sync_complete=self._on_orchestrator_sync_complete,
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

    def _on_orchestrator_sync_complete(self, result) -> None:
        """Handle sync completion callback from orchestrator."""
        if result.success:
            logger.debug(f"[UIContainer] Orchestrator sync: {result.count} devices")

    def _init_controllers(self) -> None:
        """Initialize all controllers with proper dependencies."""
        device_presenter = DevicePresenter()
        gantt_presenter = GanttPresenter()

        config_path = None
        mssql_url = None
        remote_source = None

        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            config_path = PATHS.device_positions_path
        except ImportError:
            pass

        # Get infrastructure from app container
        try:
            if hasattr(self._app, "db_config") and self._app.db_config:
                mssql_url = self._app.db_config.mssql_url
                logger.info("[UIContainer] Got MSSQL URL from config")

            if hasattr(self._app, "remote_source") and self._app.remote_source:
                remote_source = self._app.remote_source
                logger.info("[UIContainer] Got remote data source from app container")
        except Exception as e:
            logger.warning(f"[UIContainer] Could not get remote config: {e}")

        # Shell controller
        self._shell_controller = ShellController(
            store=self._store,
            config_path=config_path,
            page_manager=self._page_manager,
        )

        # Device controller with SyncOrchestrator (new API)
        self._device_controller = DeviceController(
            device_service=None,  # Legacy - not used
            presenter=device_presenter,
            store=self._store,
            page_manager=self._page_manager,
            remote_source=remote_source,
            sync_orchestrator=self._sync_orchestrator,  # NEW: Inject orchestrator
        )

        # Gantt controller
        self._gantt_controller = GanttController(
            device_service=None,
            presenter=gantt_presenter,
            store=self._store,
            mssql_url=mssql_url,
        )

        logger.info("[UIContainer] Controllers initialized")

    def _init_main_window(self) -> None:
        """Initialize main window."""
        self._main_window = MainWindow(
            store=self._store,
            shell_controller=self._shell_controller,
            page_manager=self._page_manager,
        )

    def _wire_gantt_to_window(self) -> None:
        """Wire Gantt controller to main window."""
        if self._main_window and self._gantt_controller:
            self._main_window.set_gantt_controller(self._gantt_controller)
            logger.info("[UIContainer] Gantt controller wired to MainWindow")

    def _connect_signals(self) -> None:
        """Connect component signals."""
        if self._store and self._page_manager:
            self._store.page_changed.connect(self._on_store_page_changed)

        if self._device_controller:
            self._device_controller.sync_completed.connect(self._on_device_sync_completed)

    def _init_auto_refresh(self) -> None:
        """Initialize auto-refresh timer for latest status."""
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(AUTO_REFRESH_INTERVAL_MS)
        self._refresh_timer.timeout.connect(self._on_auto_refresh)

        logger.info(f"[UIContainer] Auto-refresh timer configured " f"({AUTO_REFRESH_INTERVAL_MS}ms interval)")

    # -------------------------------------------------------------------------
    # Signal Handlers
    # -------------------------------------------------------------------------

    def _on_store_page_changed(self, page: str) -> None:
        """Handle page change from store."""
        logger.debug(f"[UIContainer] Store page changed to {page}")

    def _on_device_sync_completed(self, count: int) -> None:
        """Handle device sync completion."""
        logger.debug(f"[UIContainer] Device sync completed: {count} devices")

    def _on_auto_refresh(self) -> None:
        """
        Auto-refresh callback - sync current page devices.

        This method:
        1. Gets current page device IDs from PageDeviceManager
        2. Passes explicit device IDs to DeviceController
        3. DeviceController uses SyncOrchestrator with explicit IDs
        """
        if self._is_shutting_down:
            return

        if self._device_controller and self._page_manager:
            # Get device IDs for current page (Presentation Layer determines this)
            current_device_ids = self._page_manager.get_current_devices()

            # Pass explicit device IDs to controller
            # Controller will forward to SyncOrchestrator
            self._device_controller.sync_devices(current_device_ids)

            # Also sync incremental history if orchestrator is available
            self._sync_incremental_history(current_device_ids)

    def _sync_incremental_history(self, device_ids: list) -> None:
        """Sync incremental history during auto-refresh."""
        if not self._sync_orchestrator or not device_ids:
            return

        # Use AsyncExecutor from device controller or create task
        try:
            from ..adapters.async_executor import AsyncExecutor

            # Create a one-off executor for history sync
            executor = getattr(self, "_history_executor", None)
            if not executor:
                executor = AsyncExecutor(max_workers=1, parent=self)
                self._history_executor = executor

            executor.execute(
                self._sync_orchestrator.sync_incremental_history(device_ids),
                on_success=lambda r: logger.debug(f"[UIContainer] Incremental history: {r.records_synced} records"),
                on_error=lambda e: logger.debug(f"[UIContainer] Incremental history error: {e}"),
            )
        except Exception as e:
            logger.debug(f"[UIContainer] Could not sync incremental history: {e}")

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    def schedule_deferred_data_load(self) -> None:
        """Schedule initial data load after UI is shown."""
        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._start_data_loading)

    def _start_data_loading(self) -> None:
        """
        Start loading data for current page and start auto-refresh.

        Initial load sequence:
        1. Sync latest status for current page devices
        2. Sync initial history for current page devices
        3. Start auto-refresh timer
        """
        if self._initial_load_done:
            return

        self._initial_load_done = True
        logger.info("[UIContainer] Starting initial data load...")

        if self._device_controller and self._page_manager:
            # Get current page device IDs
            current_device_ids = self._page_manager.get_current_devices()
            logger.info(f"[UIContainer] Initial sync for {len(current_device_ids)} devices")

            # Sync latest status with explicit device IDs
            self._device_controller.sync_devices(current_device_ids)

            # Sync initial history (separate operation)
            self._sync_initial_history(current_device_ids)

        # Start auto-refresh timer
        if self._refresh_timer:
            self._refresh_timer.start()
            logger.info("[UIContainer] Auto-refresh timer started")

        logger.info("[UIContainer] Initial data load started")

    def _sync_initial_history(self, device_ids: list) -> None:
        """Sync initial history for devices on startup."""
        if not self._sync_orchestrator or not device_ids:
            return

        try:
            from ..adapters.async_executor import AsyncExecutor

            executor = getattr(self, "_history_executor", None)
            if not executor:
                executor = AsyncExecutor(max_workers=1, parent=self)
                self._history_executor = executor

            # Sync initial history with explicit device IDs
            executor.execute(
                self._sync_orchestrator.sync_initial_history(device_ids),
                on_success=lambda r: logger.info(
                    f"[UIContainer] Initial history synced: {r.records_synced} records " f"for {r.devices_processed} devices"
                ),
                on_error=lambda e: logger.warning(f"[UIContainer] Initial history sync failed: {e}"),
            )
        except Exception as e:
            logger.warning(f"[UIContainer] Could not start initial history sync: {e}")

    def get_main_window(self) -> Optional[MainWindow]:
        """Get main window instance."""
        return self._main_window

    def get_gantt_controller(self) -> Optional[GanttController]:
        """Get Gantt controller."""
        return self._gantt_controller

    def get_device_controller(self) -> Optional[DeviceController]:
        """Get device controller."""
        return self._device_controller

    def get_page_manager(self) -> Optional[PageDeviceManager]:
        """Get page device manager."""
        return self._page_manager

    def get_sync_orchestrator(self) -> Optional["SyncOrchestrator"]:
        """Get sync orchestrator."""
        return self._sync_orchestrator

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def shutdown(self) -> None:
        """Shutdown all UI components gracefully."""
        if not self._is_initialized:
            return

        # Mark as shutting down to prevent new operations
        self._is_shutting_down = True

        logger.info("[UIContainer] Shutting down...")

        # Stop timers first
        if self._refresh_timer:
            self._refresh_timer.stop()
            self._refresh_timer.deleteLater()
            self._refresh_timer = None
            logger.info("[UIContainer] Auto-refresh timer stopped")

        # Stop history executor if exists
        if hasattr(self, "_history_executor") and self._history_executor:
            self._history_executor.shutdown(wait=False)
            self._history_executor = None

        # Disconnect signals
        self._disconnect_signals()

        # Shutdown controllers
        if self._device_controller:
            self._device_controller.shutdown()

        if self._gantt_controller:
            self._gantt_controller.shutdown()

        # Close main window
        if self._main_window:
            self._main_window.close()

        self._is_initialized = False
        logger.info("[UIContainer] Shutdown complete")

    def _disconnect_signals(self) -> None:
        """Disconnect all signal connections."""
        if self._store:
            try:
                self._store.page_changed.disconnect(self._on_store_page_changed)
            except RuntimeError:
                pass

        if self._device_controller:
            try:
                self._device_controller.sync_completed.disconnect(self._on_device_sync_completed)
            except RuntimeError:
                pass


__all__ = ["UIContainer"]
