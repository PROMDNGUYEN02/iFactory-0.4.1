# File: presentation/di/container.py
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
from ..state.reducers import INITIAL_STATE
from ..state.store import Store
from ..views.main_window import MainWindow

if TYPE_CHECKING:
    from iFactory.shared.di.app_container import AppContainer

logger = logging.getLogger(__name__)


class UIContainer(QObject):
    def __init__(self, app_container: "AppContainer"):
        super().__init__()
        self._app = app_container
        self._is_initialized = False
        self._initial_load_done = False
        self._gantt_loaded = False

        self._store: Optional[Store] = None
        self._main_window: Optional[MainWindow] = None

        self._shell_controller: Optional[ShellController] = None
        self._device_controller: Optional[DeviceController] = None
        self._gantt_controller: Optional[GanttController] = None

    def initialize(self) -> None:
        if self._is_initialized:
            logger.debug("UIContainer already initialized")
            return

        logger.info("UIContainer initializing...")

        self._init_store()
        self._init_controllers()
        self._init_main_window()
        self._connect_signals()

        self._is_initialized = True

        logger.info("UIContainer initialized successfully")

    def _init_store(self) -> None:
        self._store = Store(INITIAL_STATE)

    def _init_controllers(self) -> None:
        device_presenter = DevicePresenter()
        gantt_presenter = GanttPresenter()

        config_path = None
        try:
            from iFactory.infrastructure.configuration.paths import PATHS

            config_path = PATHS.device_positions_path
        except ImportError:
            pass

        self._shell_controller = ShellController(
            store=self._store,
            config_path=config_path,
        )

        self._device_controller = DeviceController(
            device_service=self._app.device_facade,
            presenter=device_presenter,
            store=self._store,
        )

        self._gantt_controller = GanttController(
            device_service=self._app.device_facade,
            presenter=gantt_presenter,
            store=self._store,
        )

    def _init_main_window(self) -> None:
        self._main_window = MainWindow(
            store=self._store,
            shell_controller=self._shell_controller,
        )

    def _connect_signals(self) -> None:
        """Connect store state changes to trigger gantt loading."""
        if self._store:
            self._store.state_changed.connect(self._on_state_changed)

    def _on_state_changed(self, state: dict) -> None:
        """Load gantt when devices are first loaded."""
        if self._gantt_loaded:
            return

        devices = state.get("devices", {})
        if devices and len(devices) > 0:
            self._gantt_loaded = True
            logger.info(f"Devices loaded ({len(devices)}), now loading gantt...")

            # Delay gantt load slightly to ensure state is stable
            QTimer.singleShot(500, self._load_gantt)

    def _load_gantt(self) -> None:
        """Load gantt timeline data."""
        if self._gantt_controller:
            self._gantt_controller.load_timeline(days=1)

    def schedule_deferred_data_load(self) -> None:
        QTimer.singleShot(Timing.DEFERRED_LOAD_DELAY_MS, self._start_data_loading)

    def _start_data_loading(self) -> None:
        if self._initial_load_done:
            return

        self._initial_load_done = True
        logger.info("Starting data controllers...")

        if self._device_controller:
            self._device_controller.start_polling()

        # Don't load gantt here - wait for devices to be loaded first
        # Gantt will be loaded in _on_state_changed when devices are available

        logger.info("Data controllers started")

    def get_main_window(self) -> Optional[MainWindow]:
        return self._main_window

    def get_gantt_controller(self) -> Optional[GanttController]:
        return self._gantt_controller

    def get_device_controller(self) -> Optional[DeviceController]:
        return self._device_controller

    def shutdown(self) -> None:
        if not self._is_initialized:
            return

        logger.info("UIContainer shutting down...")

        # Disconnect signals
        if self._store:
            try:
                self._store.state_changed.disconnect(self._on_state_changed)
            except RuntimeError:
                pass

        if self._device_controller:
            self._device_controller.shutdown()

        if self._gantt_controller:
            self._gantt_controller.shutdown()

        if self._main_window:
            self._main_window.close()

        logger.info("UIContainer shutdown complete")


__all__ = ["UIContainer"]
