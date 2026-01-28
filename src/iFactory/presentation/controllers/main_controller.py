"""
Main Controller - Handles UI navigation and theme use cases.
Single Responsibility: Dispatch user intent to Store.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject

from ..ui_state.actions import change_theme, navigate_page, UIActionType
from ..ui_state.store import Action

if TYPE_CHECKING:
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class MainController(QObject):
    """
    Handles main window user interactions.
    Dispatches actions to Store - NO view mutation.
    """

    def __init__(self, store: "Store", parent=None):
        super().__init__(parent)
        self._store = store

    def handle_theme_toggle(self, current_mode: str) -> None:
        """User requested theme change."""
        new_mode = "dark" if current_mode == "light" else "light"
        self._store.dispatch(change_theme(new_mode))
        logger.debug(f"[MainController] Theme changed to: {new_mode}")

    def handle_navigation(self, page_name: str) -> None:
        """User clicked a menu item."""
        self._store.dispatch(navigate_page(page_name))
        logger.debug(f"[MainController] Navigated to: {page_name}")

    def handle_left_menu_toggle(self) -> None:
        """Toggle left menu visibility."""
        self._store.dispatch(Action(type=UIActionType.LEFT_MENU_TOGGLED.value))

    def handle_right_panel_toggle(self) -> None:
        """Toggle right panel visibility."""
        self._store.dispatch(Action(type=UIActionType.RIGHT_PANEL_TOGGLED.value))

    def handle_device_selection(self, device_id: str) -> None:
        """User selected a device."""
        # Local import to avoid circular dependency in tight coupling scenarios
        from ..ui_state.actions import select_device

        self._store.dispatch(select_device(device_id))
        logger.debug(f"[MainController] Device selected: {device_id}")
