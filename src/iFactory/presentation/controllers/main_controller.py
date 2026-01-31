"""
Main Controller - Application Orchestrator.
Mediates between User Intents and Application State.
Handles UI Configuration Loading to keep Widgets pure.
"""

from __future__ import annotations

import logging
import json
from typing import TYPE_CHECKING, Dict, Any
from PySide6.QtCore import QObject

# Action Dispatchers
from ..ui_state.actions import change_theme, navigate_page, toggle_left_menu, toggle_right_panel, select_device, set_data_range

if TYPE_CHECKING:
    from ..ui_state.store import Store

logger = logging.getLogger(__name__)


class MainController(QObject):
    """
    Primary Controller for the Application Shell.
    Responsible for:
    1. Receiving user inputs (Intents).
    2. Validating intents.
    3. Dispatching Actions to the Store.
    4. Providing UI Configuration (Layouts) to Views.
    """

    def __init__(self, store: "Store", parent=None):
        super().__init__(parent)
        self._store = store

    def handle_theme_toggle(self, current_mode: str) -> None:
        """Intent: User wants to toggle visual theme."""
        new_mode = "dark" if current_mode == "light" else "light"
        self._store.dispatch(change_theme(new_mode))
        logger.info(f"[Controller] Theme changed to: {new_mode}")

    def handle_navigation(self, page_name: str) -> None:
        """Intent: User wants to switch main workspace page."""
        self._store.dispatch(navigate_page(page_name))

    def handle_left_menu_toggle(self) -> None:
        """Intent: User toggles the main navigation sidebar."""
        self._store.dispatch(toggle_left_menu())

    def handle_right_panel_toggle(self) -> None:
        """Intent: User toggles the details/settings panel."""
        self._store.dispatch(toggle_right_panel())

    def handle_device_selection(self, device_id: str) -> None:
        """
        Intent: User clicked a specific device.
        Action: Select device AND ensure details panel is visible (UX Rule).
        """
        self._store.dispatch(select_device(device_id))

        # UX: Automatically open the info panel if it's currently closed
        state = self._store.get_state()
        if not state.get("right_panel_expanded", False):
            self._store.dispatch(toggle_right_panel())

    def handle_data_range_change(self, days: int) -> None:
        """Intent: User changed the historical data filter."""
        self._store.dispatch(set_data_range(days))
        self._trigger_context_refresh()

    def handle_refresh_request(self) -> None:
        """Intent: User manually requested data refresh."""
        self._trigger_context_refresh()

    def get_layout_config(self, area_key: str) -> Dict[str, Any]:
        """
        Retrieves layout configuration for a specific area.
        Moves Infrastructure I/O out of UI Widgets to ensure they remain Pure Components.
        """
        try:
            # Lazy import to avoid circular dependencies and keep module clean
            from iFactory.infrastructure.configuration.paths import PATHS

            if not PATHS.device_positions_path.exists():
                logger.warning(f"[Controller] Layout config not found: {PATHS.device_positions_path}")
                return {}

            # Read and parse configuration
            text = PATHS.device_positions_path.read_text(encoding="utf-8")
            data = json.loads(text)

            # Robustness: Handle typical typos in config keys (e.g. 'daboard' vs 'dashboard')
            # This ensures the UI doesn't break if the JSON has legacy keys
            config = data.get(area_key, {})
            if not config:
                # Fallback search if exact key match fails
                for key in data.keys():
                    if key in area_key or area_key in key:
                        return data[key]

            return config

        except Exception as e:
            logger.error(f"[Controller] Failed to load layout config for {area_key}: {e}")
            return {}

    def _trigger_context_refresh(self) -> None:
        """Helper: Refreshes currently selected item to reflect global filter changes."""
        state = self._store.get_state()
        selected_id = state.get("selected_device_id")
        if selected_id:
            self._store.dispatch(select_device(selected_id))
