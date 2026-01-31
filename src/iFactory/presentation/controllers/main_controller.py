"""
Main Controller - Application Orchestrator.
Handles user intents, dispatches actions, and bridges UI to Application layer.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING
from PySide6.QtCore import QObject

from ..ui_state.actions import change_theme, navigate_page, toggle_left_menu, toggle_right_panel, select_device, set_data_range

if TYPE_CHECKING:
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class MainController(QObject):
    """
    Mediator between UI Components and the Redux Store.
    Purely responsible for dispatching Actions based on user input.
    """

    def __init__(self, store: "Store", parent=None):
        super().__init__(parent)
        self._store = store

    def handle_theme_toggle(self, current_mode: str) -> None:
        """Switch between light and dark themes."""
        new_mode = "dark" if current_mode == "light" else "light"
        self._store.dispatch(change_theme(new_mode))
        logger.info(f"[Controller] Theme toggled to: {new_mode}")

    def handle_navigation(self, page_name: str) -> None:
        """Navigate to a specific application page."""
        self._store.dispatch(navigate_page(page_name))
        logger.debug(f"[Controller] Navigation requested: {page_name}")

    def handle_left_menu_toggle(self) -> None:
        """Toggle the sidebar menu visibility."""
        self._store.dispatch(toggle_left_menu())

    def handle_right_panel_toggle(self) -> None:
        """Toggle the details panel visibility."""
        self._store.dispatch(toggle_right_panel())

    def handle_device_selection(self, device_id: str) -> None:
        """Select a device and ensure the details panel is open."""
        self._store.dispatch(select_device(device_id))

        # Auto-open panel if closed
        state = self._store.get_state()
        if not state.get("right_panel_expanded", False):
            self._store.dispatch(toggle_right_panel())

        logger.debug(f"[Controller] Device selected: {device_id}")

    def handle_data_range_change(self, days: int) -> None:
        """Update the historical data range filter."""
        self._store.dispatch(set_data_range(days))

        # Trigger refresh via re-selection or generic refresh if available
        # Ideally, this should trigger a use case reload
        logger.info(f"[Controller] Data range set to {days} days")

        # Re-trigger selection to refresh view if a device is selected
        state = self._store.get_state()
        selected_id = state.get("selected_device_id")
        if selected_id:
            self._store.dispatch(select_device(selected_id))

    def handle_refresh_data(self) -> None:
        """Manual data refresh request."""
        # Implementation depends on how data fetching is wired (polling vs push)
        # This acts as a placeholder for manual refresh intents
        pass
