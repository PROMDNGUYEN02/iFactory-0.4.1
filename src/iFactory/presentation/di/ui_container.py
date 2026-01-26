"""
UI Dependency Injection Container.
Wires the Presentation Layer (Redux Store, Controllers, Views).
"""

import logging
import asyncio
from PySide6.QtCore import QObject

from ..ui_state.store import Store
from ..ui_state.reducers import root_reducer
from ..presenters.device_presenter import DevicePresenter
from ..controllers.main_controller import MainController
from ..controllers.device_controller import DeviceController
from ..views.main_view import MainView

logger = logging.getLogger(__name__)


class UIContainer(QObject):
    """
    Initializes the Presentation layer components in the correct order.
    """

    def __init__(self, app_container):
        super().__init__()
        self.app_container = app_container
        self._store = None
        self._main_view = None
        self._device_controller = None

    def initialize(self):
        """Wire up the Redux architecture."""
        logger.info("[UIContainer] Initializing Presentation Layer...")

        # 1. Initialize Redux Store
        initial_state = {"theme": "light", "current_page": "daboard_page", "devices": {}, "left_menu_expanded": True, "right_panel_expanded": False}
        self._store = Store(initial_state, {"root": root_reducer})

        # 2. Initialize Presenters
        device_presenter = DevicePresenter()

        # 3. Initialize Controllers
        main_controller = MainController(store=self._store)
        self._device_controller = DeviceController(device_service=self.app_container.device_facade, presenter=device_presenter, store=self._store)

        # 4. Initialize Main View (Reactive)
        self._main_view = MainView(store=self._store, controller=main_controller)

        logger.info("[UIContainer] Presentation Layer initialized.")

    def get_main_window(self):
        """Returns the fully wired main window."""
        return self._main_view

    def schedule_deferred_data_load(self):
        """
        Called by ApplicationRunner after UI is shown.
        Loads initial data in the background without freezing the UI.
        """
        if self._device_controller:
            logger.debug("[UIContainer] Triggering initial data load...")
            # Sử dụng event loop hiện tại để tránh lỗi "no running event loop"
            loop = asyncio.get_event_loop()
            loop.create_task(self._device_controller.refresh_all_devices())

    def shutdown(self):
        """Clean up resources."""
        if self._main_view:
            self._main_view.close()


__all__ = ["UIContainer"]
