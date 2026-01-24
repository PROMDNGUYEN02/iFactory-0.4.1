# File: src/iFactory/presentation/managers/menu_manager.py
"""
Menu Manager - Manages left sidebar menu items and navigation.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QListWidget, QAbstractItemView, QFrame

from iFactory.presentation.managers.widgets.menu_widgets import MenuItemWidget

__all__ = ["MenuManager"]


class MenuManager:
    """Manages left sidebar menu items and navigation."""

    __slots__ = (
        "_main_list",
        "_settings_list",
        "_icons",
        "_constants",
        "_menu_items",
        "_page_mapping",
    )

    def __init__(
        self,
        main_list: QListWidget,
        settings_list: QListWidget,
        icon_manager: Any,
        constants: Any,
    ):
        """Initialize menu manager."""
        self._main_list = main_list
        self._settings_list = settings_list
        self._icons = icon_manager
        self._constants = constants
        self._menu_items = list = []
        self._page_mapping: Dict[str, str] = {}

    def set_menu_items(
        self,
        items: list,
        page_mapping: Optional[Dict[str, str]] = None,
    ) -> None:
        """Set menu items using MenuItemWidget for text labels."""
        self._menu_items = items
        self._page_mapping = page_mapping or {}
        self._main_list.setUpdatesEnabled(False)
        try:
            self._main_list.clear()
            for item in items:
                icon = getattr(item, "icon", "")
                title = getattr(item, "title", str(item))
                shortcut = getattr(item, "shortcut", "")
                self._add_main_item(self._main_list, icon, title, shortcut)
                if getattr(item, "settings_page", None):
                    self._add_settings_item(self._settings_list, icon, title, shortcut)
        finally:
            self._main_list.setUpdatesEnabled(True)

    def add_settings_item(
        self,
        icon_resource: str, title: str, shortcut: str = "",
    ) -> None:
        """Add settings item to settings list."""
        self._settings_list.setUpdatesEnabled(False)
        try:
            self._settings_list.clear()
            self._add_settings_item(self._settings_list, icon_resource, title, shortcut)
        finally:
            self._settings_list.setUpdatesEnabled(True)

    def _add_main_item(
        self,
        widget: QListWidget,
        icon_res: str,
        title: str,
        shortcut: str = "",
    ) -> None:
        """Add main item to list widget."""
        icon = self._icons.icon(icon_res, self._constants.ICON_SIZE)
        item = MenuItemWidget(self, icon_res, title, shortcut, theme=self._constants.THEME)
        widget.addItem(item)

    def _add_settings_item(
        self,
        widget: QListWidget,
        icon_res: str,
        title: str,
        shortcut: str = "",
    ) -> None:
        """Add settings item to settings list."""
        icon = self._icons.icon(icon_res, self._constants.ICON_SIZE)
        item = MenuItemWidget(self, icon_res, title, shortcut, theme=self._constants.THEME)
        widget.addItem(item)

    def get_page_for_item(self, row: int) -> Optional[str]:
        """Get page name for menu row."""
        if 0 <= row < len(self._menu_items):
            item = self._menu_items[row]
            title = getattr(item, "title", str(item))
            return self._page_mapping.get(title)
        return None

    def clear_selection(self) -> None:
        """Clear all selections."""
        self._main_list.setCurrentRow(-1)
        self._main_list.clearSelection()
        self._settings_list.setCurrentRow(-1)
        self._settings_list.clearSelection()

    def set_collapsed(self, collapsed: bool) -> None:
        """Set collapsed state for menu lists."""
        for widget in (self._main_list, self._settings_list):
            widget.setProperty("collapsed", collapsed)
            widget.style().unpolish(widget)
            widget.style().polish(widget)
            widget.viewport().update()

    def refresh_icons(self) -> None:
        """Refresh all icons with current theme."""
        for i, item in enumerate(self._menu_items):
            list_item = self._main_list.item(i)
            if list_item:
                icon = getattr(item, "icon", "")
                settings_item = self._settings_list.item(0)
                if settings_item:
                    settings_item.refresh_theme(self._constants.THEME)

    @property
    def menu_items(self) -> list:
        """Return menu items."""
        return self._menu_items.copy()

    @property
    def page_mapping(self) -> Dict[str, str]:
        """Return page mapping."""
        return self._page_mapping.copy()
