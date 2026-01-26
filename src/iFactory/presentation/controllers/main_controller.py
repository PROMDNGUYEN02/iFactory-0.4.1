"""
Main Controller - Orchestrates UI Intent to Application Actions.
Clean Architecture Compliant: NO direct UI imports, NO direct view mutation.
"""

from __future__ import annotations
import logging
from PySide6.QtCore import QObject
from ..ui_state.actions import change_theme, navigate_page, UIActionType
from ..ui_state.store import Action

logger = logging.getLogger(__name__)


class MainController(QObject):
    """
    Handles user intent from the main window.
    Dispatches actions to the Redux store.
    """

    def __init__(self, store, parent=None):
        super().__init__(parent)
        self._store = store
        logger.debug("[MainController] Initialized.")

    def handle_theme_toggle(self, current_mode: str) -> None:
        """User requested theme change."""
        new_mode = "dark" if current_mode == "light" else "light"
        self._store.dispatch(change_theme(new_mode))

    def handle_navigation(self, page_name: str) -> None:
        """User clicked a menu item."""
        self._store.dispatch(navigate_page(page_name))

    def handle_left_menu_toggle(self) -> None:
        """Toggle left menu visibility state."""
        # A generic action to toggle menu state
        self._store.dispatch(Action(type=UIActionType.LEFT_MENU_TOGGLED.value))

    def handle_right_panel_toggle(self) -> None:
        """Toggle right panel visibility state."""
        self._store.dispatch(Action(type=UIActionType.RIGHT_PANEL_TOGGLED.value))


__all__ = ["MainController"]
