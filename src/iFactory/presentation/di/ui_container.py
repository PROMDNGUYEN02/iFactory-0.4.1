"""
UI Dependency Injection Container.
Responsible for wiring the Presentation Layer graph.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, QTimer

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
    Composition Root for the Presentation Layer.
    """

    def __init__(self, app_container: "AppContainer"):
        super().__init__()
        self._app_container = app_container

        # State
        self._store: Store | None = None

        # Views & Controllers
        self._main_view: MainView | None = None
        self._main_controller: MainController | None = None
        self._device_controller: DeviceController | None = None
        self._gantt_controller: GanttController | None = None

    def initialize(self) -> None:
        """Initialize and wire components."""
        logger.info("[UIContainer] Initializing Presentation Layer...")

        # 1. Setup State Store
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
        }
        self._store = Store(initial_state, {"root": root_reducer})

        # 2. Setup Presenters (Pure Transformers)
        device_presenter = DevicePresenter()
        gantt_presenter = GanttPresenter()

        # 3. Setup Controllers (Orchestrators)
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

        # 4. Setup Main View
        self._main_view = MainView(
            store=self._store,
            controller=self._main_controller,
        )

        # 5. Kickoff Lifecycle
        QTimer.singleShot(100, self._setup_initial_view)

        logger.info("[UIContainer] Presentation Layer initialized.")

    def _setup_initial_view(self) -> None:
        """Finalize view configuration after loop start."""
        if self._main_view is None:
            return

        try:
            # Defensive coding against specific UI implementation details
            if hasattr(self._main_view, "ui"):
                if hasattr(self._main_view.ui, "listWidget"):
                    self._main_view.ui.listWidget.setCurrentRow(0)
                if hasattr(self._main_view.ui, "stackedWidget"):
                    self._main_view.ui.stackedWidget.setCurrentIndex(0)

            # Schedule initial data fetch
            QTimer.singleShot(500, self._trigger_data_load)

        except Exception as e:
            logger.warning(f"Could not set initial view state: {e}")

    def _trigger_data_load(self) -> None:
        """Bridge sync timer to async loader."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.ensure_future(self._load_all_data())
            else:
                loop.run_until_complete(self._load_all_data())
        except Exception as e:
            logger.debug(f"Data load scheduling failed: {e}")

    async def _load_all_data(self) -> None:
        """Execute initial data loading use cases."""
        try:
            if self._device_controller:
                await self._device_controller.refresh_all_devices()

            if self._gantt_controller:
                await self._gantt_controller.load_timeline(days=1)

        except Exception as e:
            logger.error(f"Failed to load initial data: {e}")

    def get_main_window(self) -> MainView | None:
        return self._main_view

    def shutdown(self) -> None:
        """Clean shutdown of presentation layer."""
        if self._device_controller:
            self._device_controller.stop_polling()

        if self._main_view:
            self._main_view.close()
        logger.info("[UIContainer] Shutdown complete.")
