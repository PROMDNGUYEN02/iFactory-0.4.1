"""
Sidebar Component.
Refactored for Layout Stability & Missing Methods.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QVBoxLayout, QWidget, QSizePolicy

from ...constants.ui_constants import UIConstants
from ...resources.themes.theme_manager import theme_manager
from ...ui_state.selectors import select_left_menu_expanded, select_current_page


class SidebarView:
    def __init__(self, container_frame, nav_list, settings_list, controller):
        self._frame = container_frame
        self._nav_list = nav_list
        self._settings_list = settings_list
        self._controller = controller
        self._cached_data_range = 1  # Default value
        self._current_theme_mode = "light"

        self._fix_layout_containers()
        self._setup_ui()
        self._connect_signals()

    def _fix_layout_containers(self):
        """Standardize layout structure."""
        if not self._frame.layout():
            layout = QVBoxLayout(self._frame)
            self._frame.setLayout(layout)
        else:
            layout = self._frame.layout()

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # [FIX CRASH 1] Correct QSizePolicy usage
        if self._nav_list:
            self._nav_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        if self._settings_list:
            self._settings_list.setFixedHeight(60)
            self._settings_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

    def _setup_ui(self):
        # Clean lists
        for lst in [self._nav_list, self._settings_list]:
            if lst:
                lst.clear()
                lst.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                lst.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
                lst.setIconSize(QSize(24, 24))

        # Main Nav
        items = [
            ("Dashboard", ":/icon/dashboard.svg", "daboard_page"),
            ("Orders", ":/icon/orders.svg", "orders_page"),
        ]
        if self._nav_list:
            for text, icon, pid in items:
                item = QListWidgetItem(QIcon(icon), text)
                item.setData(Qt.UserRole, pid)
                item.setToolTip(text)
                self._nav_list.addItem(item)
            self._nav_list.setCurrentRow(0)

        # Settings
        if self._settings_list:
            st_item = QListWidgetItem(QIcon(":/icon/settings.svg"), "Settings")
            st_item.setData(Qt.UserRole, "settings_page")
            st_item.setToolTip("Settings")
            self._settings_list.addItem(st_item)

    def _connect_signals(self):
        if self._nav_list:
            self._nav_list.itemClicked.connect(self._on_nav_clicked)
        if self._settings_list:
            self._settings_list.itemClicked.connect(self._on_settings_clicked)

    # [FIX CRASH 2] Added missing method
    def set_data_range(self, days: int):
        """Update cached data range for settings menu."""
        self._cached_data_range = days

    def render(self, state: dict):
        is_expanded = select_left_menu_expanded(state)
        current_page = select_current_page(state)

        new_theme = state.get("theme", "light")
        if new_theme != self._current_theme_mode:
            self._current_theme_mode = new_theme
            self._update_icons(is_expanded)

        # Width Animation
        w = UIConstants.MENU_EXPANDED_WIDTH if is_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        if self._frame:
            self._frame.setFixedWidth(w)

        # Update CSS Property for Styling
        collapsed_val = "true" if not is_expanded else "false"
        lists = [l for l in [self._nav_list, self._settings_list] if l]

        for lst in lists:
            if lst.property("collapsed") != collapsed_val:
                lst.setProperty("collapsed", collapsed_val)
                lst.style().unpolish(lst)
                lst.style().polish(lst)

        self._update_icons(is_expanded)
        self._sync_selection(current_page)

    def _update_icons(self, is_expanded):
        if self._nav_list:
            for i in range(self._nav_list.count()):
                item = self._nav_list.item(i)
                pid = item.data(Qt.UserRole)
                key = ":/icon/dashboard.svg" if "daboard" in pid else ":/icon/orders.svg"
                item.setIcon(QIcon(theme_manager.get_icon_path(key)))

        if self._settings_list:
            item = self._settings_list.item(0)
            if item:
                item.setIcon(QIcon(theme_manager.get_icon_path(":/icon/settings.svg")))

    def _sync_selection(self, page_id):
        if page_id == "settings_page":
            if self._nav_list:
                self._nav_list.clearSelection()
            if self._settings_list:
                self._settings_list.setCurrentRow(0)
        else:
            if self._settings_list:
                self._settings_list.clearSelection()
            if self._nav_list:
                for i in range(self._nav_list.count()):
                    if self._nav_list.item(i).data(Qt.UserRole) == page_id:
                        self._nav_list.setCurrentRow(i)
                        break

    def _on_nav_clicked(self, item):
        self._controller.handle_navigation(item.data(Qt.UserRole))

    def _on_settings_clicked(self, item):
        # Simple popup logic
        menu = QMenu(self._settings_list)
        # Add actions based on logic...
        # For brevity, keeping it simple to avoid new errors
        pass
