"""
UI Dependency Injection Container.
Wires the Presentation Layer components.
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

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
    """Initializes Presentation layer components."""

    def __init__(self, app_container: "AppContainer"):
        super().__init__()
        self._app_container = app_container
        self._store: Store | None = None
        self._main_view: MainView | None = None
        self._device_controller: DeviceController | None = None
        self._gantt_controller: GanttController | None = None

    def initialize(self) -> None:
        """Wire up all presentation components."""
        logger.info("[UIContainer] Initializing Presentation Layer...")

        initial_state = {
            "theme": "light",
            "current_page": "daboard_page",
            "devices": {},
            "gantt_timeline": {},
            "left_menu_expanded": False,
            "right_panel_expanded": False,
            "selected_device_id": None,
            "is_loading": False,
            "last_error": None,
        }
        self._store = Store(initial_state, {"root": root_reducer})

        device_presenter = DevicePresenter()
        gantt_presenter = GanttPresenter()

        main_controller = MainController(store=self._store)

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

        self._main_view = MainView(
            store=self._store,
            controller=main_controller,
        )

        logger.info("[UIContainer] Presentation Layer initialized.")

    def get_main_window(self) -> MainView | None:
        return self._main_view

    def schedule_deferred_data_load(self) -> None:
        """Load initial data after UI is shown."""
        if self._device_controller:
            logger.debug("[UIContainer] Scheduling initial data load...")
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._device_controller.refresh_all_devices())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(self._device_controller.refresh_all_devices())

    def shutdown(self) -> None:
        """Clean up resources."""
        if self._main_view:
            self._main_view.close()
        logger.info("[UIContainer] Shutdown complete.")


__all__ = ["UIContainer"]
