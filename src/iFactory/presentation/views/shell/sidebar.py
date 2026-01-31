"""
Sidebar Component - Manages application navigation.
"""

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QWidget

from ...constants.ui_constants import UIConstants
from ...resources.themes.theme_manager import theme_manager
from ...ui_state.selectors import select_left_menu_expanded, select_current_page, select_data_range_days

import logging

logger = logging.getLogger(__name__)


class SidebarView:
    """
    Manages the left sidebar menu, including navigation and settings.
    """

    def __init__(self, container_frame: QWidget, nav_list: QListWidget, settings_list: QListWidget, controller):
        self._frame = container_frame
        self._nav_list = nav_list
        self._settings_list = settings_list
        self._controller = controller
        self._last_main_page_index = 0

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        """Initialize list widgets."""
        self._nav_list.clear()
        self._settings_list.clear()

        self._nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._settings_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self._settings_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        icon_size = QSize(24, 24)
        self._nav_list.setIconSize(icon_size)
        self._settings_list.setIconSize(icon_size)

        # Populate Main Navigation
        pages = [
            ("Dashboard", ":/icon/dashboard.svg", "daboard_page"),
            ("Orders", ":/icon/orders.svg", "orders_page"),
        ]
        for text, icon, page_id in pages:
            item = QListWidgetItem(QIcon(icon), text)
            item.setData(Qt.UserRole, page_id)
            item.setToolTip(text)
            self._nav_list.addItem(item)

        # Populate Settings
        settings_item = QListWidgetItem(QIcon(":/icon/settings.svg"), "Settings")
        settings_item.setData(Qt.UserRole, "settings_page")
        settings_item.setToolTip("Settings")
        self._settings_list.addItem(settings_item)

        # Initial Selection
        self._nav_list.setCurrentRow(0)

    def _connect_signals(self):
        self._nav_list.itemClicked.connect(self._on_nav_clicked)
        self._settings_list.itemClicked.connect(self._on_settings_clicked)

    def render(self, state: dict):
        """Update sidebar state based on store."""
        is_expanded = select_left_menu_expanded(state)
        current_page = select_current_page(state)

        # Update Width
        width = UIConstants.MENU_EXPANDED_WIDTH if is_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        self._frame.setFixedWidth(width)

        # Update Icons (Theme aware)
        self._update_icons(is_expanded)

        # Update Selection
        self._sync_selection(current_page)

    def _update_icons(self, is_expanded: bool):
        """Refresh icons based on theme."""
        # Main Nav
        for i in range(self._nav_list.count()):
            item = self._nav_list.item(i)
            page_id = item.data(Qt.UserRole)
            icon_key = ":/icon/dashboard.svg" if "daboard" in page_id else ":/icon/orders.svg"
            item.setIcon(QIcon(theme_manager.get_icon_path(icon_key)))

        # Settings
        item = self._settings_list.item(0)
        if item:
            item.setIcon(QIcon(theme_manager.get_icon_path(":/icon/settings.svg")))

    def _sync_selection(self, page_id: str):
        """Sync list selection with current page."""
        if page_id == "settings_page":
            # Keep visual selection on last main page to indicate context
            if self._last_main_page_index is not None:
                self._nav_list.setCurrentRow(self._last_main_page_index)
        else:
            for i in range(self._nav_list.count()):
                item = self._nav_list.item(i)
                if item.data(Qt.UserRole) == page_id:
                    self._nav_list.setCurrentRow(i)
                    self._last_main_page_index = i
                    self._settings_list.clearSelection()
                    break

    def _on_nav_clicked(self, item: QListWidgetItem):
        page_id = item.data(Qt.UserRole)
        self._last_main_page_index = self._nav_list.row(item)
        self._settings_list.clearSelection()
        self._controller.handle_navigation(page_id)

    def _on_settings_clicked(self, item: QListWidgetItem):
        """Show settings popup menu."""
        # We need the current filtering state to show checks
        # Since we don't have direct access to store here, we rely on what was rendered or fetch fresh
        # Ideally, pass state into render or have controller access.
        # For this component, we'll access the controller's store via a hack or better, passed via render.
        # But `SidebarView` doesn't hold state.
        # FIX: We will access the store via the controller if possible or assume a default.
        # Ideally state is passed in. For the popup, we'll use a callback or just ask the controller.

        # Assuming we can get the current days from the store reference in controller if we had it
        # or we just rely on the fact that this is a view.

        # Construct the menu
        menu = QMenu(self._settings_list)
        menu.setStyleSheet(
            """
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid #D3D3D3;
                padding: 4px;
                border-radius: 4px;
            }
            QMenu::item {
                padding: 6px 24px;
                font-size: 13px;
                color: #333333;
                border-radius: 4px;
            }
            QMenu::item:selected {
                background-color: #F0F0F0;
                color: #000000;
            }
            QMenu::item:checked {
                font-weight: bold;
                color: #10B981;
            }
        """
        )

        # Options
        options = [("Last 1 Day", 1), ("Last 1 Week", 7), ("Last 1 Month", 30), ("Last 3 Months", 90)]

        # We need the current selected value.
        # Since `render` happens before this click, we don't have the *latest* unless we store it.
        # We will dispatch the change blindly for now or store `data_range` in `render`.
        current_days = getattr(self, "_cached_data_range", 1)

        for text, days in options:
            action = QAction(text, menu)
            action.setCheckable(True)
            if days == current_days:
                action.setChecked(True)
            action.triggered.connect(lambda chk, d=days: self._controller.handle_data_range_change(d))
            menu.addAction(action)

        # Position
        rect = self._settings_list.visualItemRect(item)
        global_pos = self._settings_list.mapToGlobal(rect.topRight())
        menu.exec(global_pos + QPoint(5, -5))

        self._settings_list.clearSelection()

    def set_data_range(self, days: int):
        self._cached_data_range = days
