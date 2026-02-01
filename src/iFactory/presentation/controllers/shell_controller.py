"""
Shell Controller.
Manages shell/navigation state and page transitions.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import QObject, Signal

from ..state.actions import (
    deselect_device,
    select_device,
    select_device_only,
    set_data_range,
    set_page,
    set_theme,
    toggle_right_panel,
    toggle_sidebar,
)

if TYPE_CHECKING:
    from ..state.store import Store
    from ..services.page_device_manager import PageDeviceManager

logger = logging.getLogger(__name__)


class ShellController(QObject):
    """
    Controller for shell operations (navigation, theme, panels).
    """

    page_changing = Signal(str)
    page_changed = Signal(str)

    def __init__(
        self,
        store: "Store",
        config_path: Optional[Path] = None,
        page_manager: Optional["PageDeviceManager"] = None,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)
        self._store = store
        self._config_path = config_path
        self._page_manager = page_manager
        self._layout_cache: Dict[str, Any] = {}

    def set_page_manager(self, manager: "PageDeviceManager") -> None:
        """Set page manager for coordinated page changes."""
        self._page_manager = manager

    def toggle_theme(self) -> None:
        """Toggle between light and dark theme."""
        state = self._store.get_state()
        current = state.get("theme", "light")
        new_theme = "dark" if current == "light" else "light"
        self._store.dispatch(set_theme(new_theme))
        logger.info(f"Theme changed to: {new_theme}")

    def navigate_to(self, page: str) -> None:
        """Navigate to a page - triggers device sync for new page."""
        normalized = page.replace("daboard", "dashboard")
        if not normalized.endswith("_page"):
            normalized = f"{normalized}_page"

        current_page = self._store.get_state().get("current_page")

        if normalized == current_page:
            return

        logger.info(f"[ShellController] Navigating to {normalized}")

        self.page_changing.emit(normalized)

        # Update page manager - this triggers device sync
        if self._page_manager:
            self._page_manager.set_current_page(normalized)

        self._store.dispatch(set_page(normalized))
        self.page_changed.emit(normalized)

    def toggle_sidebar_menu(self) -> None:
        """Toggle sidebar expansion."""
        self._store.dispatch(toggle_sidebar())

    def toggle_details_panel(self) -> None:
        """Toggle right details panel."""
        self._store.dispatch(toggle_right_panel())

    def select_device(self, device_id: str) -> None:
        """
        Select a device and open right panel.
        Used for double-click behavior.
        """
        self._store.dispatch(select_device(device_id))

    def select_device_without_panel(self, device_id: str) -> None:
        """
        Select a device WITHOUT opening right panel.
        Used for single-click behavior - triggers gantt fetch.
        """
        self._store.dispatch(select_device_only(device_id))

    def deselect_device(self) -> None:
        """Deselect current device."""
        self._store.dispatch(deselect_device())

    def set_data_range(self, days: int) -> None:
        """Set data range for charts."""
        self._store.dispatch(set_data_range(days))

    def get_layout_config(self, area_key: str) -> Dict[str, Any]:
        """Get layout configuration for an area."""
        if area_key in self._layout_cache:
            return self._layout_cache[area_key]

        if not self._config_path or not self._config_path.exists():
            logger.warning(f"Layout config not found: {self._config_path}")
            return {}

        try:
            text = self._config_path.read_text(encoding="utf-8")
            data = json.loads(text)

            config = data.get(area_key, {})
            if not config:
                for key in data:
                    if area_key in key or key in area_key:
                        config = data[key]
                        break

            self._layout_cache[area_key] = config
            return config

        except Exception as e:
            logger.error(f"Failed to load layout config: {e}")
            return {}

    def get_current_page(self) -> str:
        """Get current page name."""
        return self._store.get_state().get("current_page", "dashboard_page")


__all__ = ["ShellController"]
