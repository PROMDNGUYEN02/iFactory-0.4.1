"""
UI Dependency Injection Container.
With auto-refresh every 3 seconds.
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

logger = logging.getLogger(__name__)

# Auto-refresh interval (3 seconds)
AUTO_REFRESH_INTERVAL_MS = 3000


class UIContainer(QObject):
    """UI Container managing all presentation components."""

    def __init__(self, app_container: "AppContainer"):
        super().__init__()
        self._app = app_container
        self._is_initialized = False
        self._initial_load_done = False
        self._is_shutting_down = False

        self._store: Optional[Store] = None
        self._page_manager: Optional[PageDeviceManager] = None
        self._main_window: Optional[MainWindow] = None

        self._shell_controller: Optional[ShellController] = None
        self._device_controller: Optional[DeviceController] = None
        self._gantt_controller: Optional[GanttController] = None

        # Auto-refresh timer
        self._refresh_timer: Optional[QTimer] = None

    def initialize(self) -> None:
        if self._is_initialized:
            return

        logger.info("[UIContainer] Initializing...")

        self._init_store()
        self._init_page_manager()
        self._init_controllers()
        self._init_main_window()
        self._connect_signals()
        self._wire_gantt_to_window()
        self._init_auto_refresh()

        self._is_initialized = True
        logger.info("[UIContainer] Initialized successfully")

    def _init_store(self) -> None:
        self._store = Store(INITIAL_STATE)

    def _init_page_manager(self) -> None:
        config_path = None
        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            config_path = PATHS.device_positions_path
        except ImportError:
            pass

        self._page_manager = PageDeviceManager(config_path=config_path)

        all_devices = self._page_manager.get_all_devices()
        logger.info(f"[UIContainer] PageDeviceManager initialized with " f"{len(all_devices)} devices")

    def _init_controllers(self) -> None:
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

        # Get MSSQL URL and remote source from app container
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

        # Device controller with remote source
        self._device_controller = DeviceController(
            device_service=None,
            presenter=device_presenter,
            store=self._store,
            page_manager=self._page_manager,
            remote_source=remote_source,
        )

        # Gantt controller
        self._gantt_controller = GanttController(
            device_service=None,
            presenter=gantt_presenter,
            store=self._store,
            mssql_url=mssql_url,
        )

    def _init_main_window(self) -> None:
        self._main_window = MainWindow(
            store=self._store,
            shell_controller=self._shell_controller,
            page_manager=self._page_manager,
        )

    def _wire_gantt_to_window(self) -> None:
        if self._main_window and self._gantt_controller:
            self._main_window.set_gantt_controller(self._gantt_controller)
            logger.info("[UIContainer] Gantt controller wired to MainWindow")

    def _connect_signals(self) -> None:
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

    def _on_store_page_changed(self, page: str) -> None:
        logger.debug(f"[UIContainer] Store page changed to {page}")

    def _on_device_sync_completed(self, count: int) -> None:
        logger.debug(f"[UIContainer] Device sync completed: {count} devices")

    def _on_auto_refresh(self) -> None:
        """Auto-refresh callback - sync current page devices."""
        # Don't refresh if shutting down
        if self._is_shutting_down:
            return

        if self._device_controller and self._page_manager:
            current_devices = self._page_manager.get_current_devices()
            self._device_controller.sync_devices(current_devices)

    def schedule_deferred_data_load(self) -> None:
        """Schedule initial data load after UI is shown."""
        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._start_data_loading)

    def _start_data_loading(self) -> None:
        """Start loading data for current page and start auto-refresh."""
        if self._initial_load_done:
            return

        self._initial_load_done = True
        logger.info("[UIContainer] Starting initial data load...")

        if self._device_controller and self._page_manager:
            current_devices = self._page_manager.get_current_devices()
            logger.info(f"[UIContainer] Initial sync for {len(current_devices)} devices")
            self._device_controller.sync_devices(current_devices)

        # Start auto-refresh timer
        if self._refresh_timer:
            self._refresh_timer.start()
            logger.info("[UIContainer] Auto-refresh timer started")

        logger.info("[UIContainer] Initial data load started")

    def get_main_window(self) -> Optional[MainWindow]:
        return self._main_window

    def get_gantt_controller(self) -> Optional[GanttController]:
        return self._gantt_controller

    def get_device_controller(self) -> Optional[DeviceController]:
        return self._device_controller

    def get_page_manager(self) -> Optional[PageDeviceManager]:
        return self._page_manager

    def shutdown(self) -> None:
        if not self._is_initialized:
            return

        # Mark as shutting down to prevent new operations
        self._is_shutting_down = True

        logger.info("[UIContainer] Shutting down...")

        # Stop auto-refresh timer first
        if self._refresh_timer:
            self._refresh_timer.stop()
            self._refresh_timer.deleteLater()
            self._refresh_timer = None
            logger.info("[UIContainer] Auto-refresh timer stopped")

        # Disconnect signals
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
            self._device_controller.shutdown()

        if self._gantt_controller:
            self._gantt_controller.shutdown()

        if self._main_window:
            self._main_window.close()

        self._is_initialized = False
        logger.info("[UIContainer] Shutdown complete")


__all__ = ["UIContainer"]
