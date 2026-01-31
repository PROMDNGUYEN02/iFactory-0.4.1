# File: presentation/views/shell/sidebar.py
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QListWidget, QListWidgetItem, QSizePolicy, QVBoxLayout

from ...constants.layout import Layout
from ...resources.themes import get_theme_manager
from ...state.selectors import select_current_page, select_sidebar_expanded, select_theme

if TYPE_CHECKING:
    from ...controllers.shell_controller import ShellController


class SidebarView:
    NAV_ITEMS = [
        ("Dashboard", ":/icon/dashboard.svg", "dashboard_page"),
        ("Orders", ":/icon/orders.svg", "orders_page"),
    ]

    def __init__(
        self,
        container: QFrame,
        nav_list: QListWidget,
        settings_list: QListWidget,
        controller: "ShellController",
    ):
        self._container = container
        self._nav_list = nav_list
        self._settings_list = settings_list
        self._controller = controller
        self._theme_manager = get_theme_manager()

        self._current_theme = "light"
        self._setup()

    def _setup(self) -> None:
        if not self._container:
            return

        layout = self._container.layout()
        if not layout:
            layout = QVBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if self._nav_list:
            self._nav_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
            self._nav_list.clear()
            self._nav_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._nav_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._nav_list.setIconSize(QSize(24, 24))

            for text, icon_path, page_id in self.NAV_ITEMS:
                item = QListWidgetItem(QIcon(icon_path), text)
                item.setData(Qt.UserRole, page_id)
                item.setToolTip(text)
                self._nav_list.addItem(item)

            self._nav_list.setCurrentRow(0)
            self._nav_list.itemClicked.connect(self._on_nav_clicked)

        if self._settings_list:
            self._settings_list.setFixedHeight(60)
            self._settings_list.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
            self._settings_list.clear()
            self._settings_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._settings_list.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
            self._settings_list.setIconSize(QSize(24, 24))

            settings_item = QListWidgetItem(QIcon(":/icon/settings.svg"), "Settings")
            settings_item.setData(Qt.UserRole, "settings_page")
            settings_item.setToolTip("Settings")
            self._settings_list.addItem(settings_item)

            self._settings_list.itemClicked.connect(self._on_settings_clicked)

    def render(self, state: dict) -> None:
        theme = select_theme(state)
        is_expanded = select_sidebar_expanded(state)
        current_page = select_current_page(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._update_icons()

        width = Layout.SIDEBAR_EXPANDED_WIDTH if is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        if self._container:
            self._container.setFixedWidth(width)

        collapsed_val = "true" if not is_expanded else "false"
        for lst in [self._nav_list, self._settings_list]:
            if lst and lst.property("collapsed") != collapsed_val:
                lst.setProperty("collapsed", collapsed_val)
                lst.style().unpolish(lst)
                lst.style().polish(lst)

        self._sync_selection(current_page)

    def _update_icons(self) -> None:
        if self._nav_list:
            for i in range(self._nav_list.count()):
                item = self._nav_list.item(i)
                page_id = item.data(Qt.UserRole)
                if "dashboard" in page_id:
                    icon_path = self._theme_manager.get_icon_path(":/icon/dashboard.svg")
                else:
                    icon_path = self._theme_manager.get_icon_path(":/icon/orders.svg")
                item.setIcon(QIcon(icon_path))

        if self._settings_list and self._settings_list.count() > 0:
            item = self._settings_list.item(0)
            icon_path = self._theme_manager.get_icon_path(":/icon/settings.svg")
            item.setIcon(QIcon(icon_path))

    def _sync_selection(self, page_id: str) -> None:
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
                    item = self._nav_list.item(i)
                    item_page = item.data(Qt.UserRole)
                    if item_page == page_id or page_id.replace("dashboard", "daboard") == item_page.replace("dashboard", "daboard"):
                        self._nav_list.setCurrentRow(i)
                        break

    def _on_nav_clicked(self, item: QListWidgetItem) -> None:
        page_id = item.data(Qt.UserRole)
        self._controller.navigate_to(page_id)

    def _on_settings_clicked(self, item: QListWidgetItem) -> None:
        pass


__all__ = ["SidebarView"]
