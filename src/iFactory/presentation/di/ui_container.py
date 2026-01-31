"""
UI Dependency Injection Container.
Composition Root for the Presentation Layer.
Handles Async Lifecycle, Dependency Wiring, and Graceful Shutdown.
"""

from __future__ import annotations

import asyncio
import logging
from threading import Thread
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QObject, QTimer

# Architecture Components
from ..ui_state.store import Store
from ..ui_state.reducers import root_reducer
from ..presenters.device_presenter import DevicePresenter
from ..presenters.gantt_presenter import GanttPresenter
from ..controllers.main_controller import MainController
from ..controllers.device_controller import DeviceController
from ..controllers.gantt_controller import GanttController
from ..views.main_view import MainView

if TYPE_CHECKING:
    from iFactory.shared.di.app_container import AppContainer

logger = logging.getLogger(__name__)


class UIContainer(QObject):
    """
    Orchestrates the creation and destruction of UI components.
    Ensures Presentation Layer is decoupled from Infrastructure at runtime.
    """

    def __init__(self, app_container: "AppContainer"):
        super().__init__()
        self._app_container = app_container

        # Lifecycle Flags
        self._is_initialized = False
        self._initial_load_triggered = False

        # Component Registry
        self._store: Optional[Store] = None
        self._main_view: Optional[MainView] = None

        # Controllers
        self._main_controller: Optional[MainController] = None
        self._device_controller: Optional[DeviceController] = None
        self._gantt_controller: Optional[GanttController] = None

        # Background Tasks
        self._init_task: Optional[asyncio.Task] = None

    def initialize(self) -> None:
        """
        Bootstraps the UI layer.
        Idempotent: Safe to call multiple times (subsequent calls are ignored).
        """
        if self._is_initialized:
            logger.debug("[UIContainer] Already initialized. Skipping.")
            return

        logger.info("[UIContainer] Bootstrapping Presentation Layer...")

        try:
            self._init_state_store()
            self._init_controllers()
            self._init_main_view()

            self._is_initialized = True

            # Fail-safe: Schedule data load if ApplicationRunner doesn't trigger it explicitly
            QTimer.singleShot(100, self._schedule_initial_data_load)

            logger.info("[UIContainer] Initialization successful.")

        except Exception as e:
            logger.critical(f"[UIContainer] Initialization FAILED: {e}", exc_info=True)
            raise

    def _init_state_store(self):
        """Setup Redux-style State Store with initial defaults."""
        initial_state = {
            "theme": "light",
            "current_page": "daboard_page",
            "devices": {},
            "gantt_timeline": {},
            "left_menu_expanded": False,
            "right_panel_expanded": False,
            "selected_device_id": None,
            "selected_menu_index": 0,
            "is_loading": False,
            "last_error": None,
            "data_range_days": 1,
            "factory_summary": {"output": 0, "yield_rate": 0.0},
        }
        self._store = Store(initial_state, {"root": root_reducer})

    def _init_controllers(self):
        """Wire Controllers with Presenters and Use Cases (via AppFacade)."""
        # Pure Logic Transformers
        device_presenter = DevicePresenter()
        gantt_presenter = GanttPresenter()

        # Business Logic Coordinators
        self._main_controller = MainController(store=self._store)

        self._device_controller = DeviceController(
            device_service=self._app_container.device_facade,
            presenter=device_presenter,
            store=self._store,
        )

        self._gantt_controller = GanttController(
            device_service=self._app_container.device_facade,
            presenter=gantt_presenter,
            store=self._store,
        )

    def _init_main_view(self):
        """Instantiate the Main Window Shell."""
        self._main_view = MainView(
            store=self._store,
            controller=self._main_controller,
        )

    def schedule_deferred_data_load(self) -> None:
        """Public method to trigger data loading from external runners."""
        self._schedule_initial_data_load()

    def _schedule_initial_data_load(self) -> None:
        """
        Bridge method to trigger async data loading.
        Smartly chooses between existing Event Loop or Background Thread.
        Idempotent: Guarantees only one execution per session.
        """
        if self._initial_load_triggered:
            # Prevents race condition between QTimer and ApplicationRunner
            return

        self._initial_load_triggered = True

        try:
            # 1. Try to find a running asyncio loop (e.g. qasync)
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop and loop.is_running():
                # Best Case: We are integrated with Qt Loop (qasync)
                self._init_task = asyncio.ensure_future(self._load_initial_data())
            else:
                # Fallback Case: No async loop found.
                # CRITICAL: Do NOT block the UI thread. Spawn a background thread.
                logger.info("[UIContainer] Using background thread for data loading (AsyncIO loop not detected).")

                def _background_loader():
                    try:
                        asyncio.run(self._load_initial_data())
                    except Exception as ex:
                        logger.error(f"[UIContainer] Background worker failed: {ex}")

                worker_thread = Thread(target=_background_loader, daemon=True)
                worker_thread.start()

        except Exception as e:
            logger.error(f"[UIContainer] Failed to schedule data load: {e}")
            # Reset flag to allow retry on error if needed
            self._initial_load_triggered = False

    async def _load_initial_data(self) -> None:
        """Execute the initial data fetch sequence."""
        logger.info("[UIContainer] Starting initial data fetch...")
        try:
            tasks = []
            if self._device_controller:
                tasks.append(self._device_controller.refresh_all_devices())

            if self._gantt_controller:
                tasks.append(self._gantt_controller.load_timeline(days=1))

            if tasks:
                await asyncio.gather(*tasks)
                logger.info("[UIContainer] Initial data fetch complete.")

        except Exception as e:
            logger.error(f"[UIContainer] Error during data fetch: {e}", exc_info=True)

    def get_main_window(self) -> MainView | None:
        return self._main_view

    def shutdown(self) -> None:
        """Graceful teardown of UI components and background tasks."""
        if not self._is_initialized:
            return

        logger.info("[UIContainer] Shutting down...")

        # Cancel pending tasks
        if self._init_task and not self._init_task.done():
            self._init_task.cancel()

        # Stop controllers
        if self._device_controller:
            self._device_controller.stop_polling()

        # Close View
        if self._main_view:
            self._main_view.close()

        logger.info("[UIContainer] Shutdown complete.")
