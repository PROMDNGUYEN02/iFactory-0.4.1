"""
Sidebar Component - Manages application navigation.
Refactored for Layout Stability.
"""

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QAction
from PySide6.QtWidgets import QListWidget, QListWidgetItem, QMenu, QWidget, QVBoxLayout, QFrame

from ...constants.ui_constants import UIConstants
from ...resources.themes.theme_manager import theme_manager
from ...ui_state.selectors import select_left_menu_expanded, select_current_page, select_data_range_days


class SidebarView:
    def __init__(self, container_frame: QWidget, nav_list: QListWidget, settings_list: QListWidget, controller):
        self._frame = container_frame
        self._nav_list = nav_list
        self._settings_list = settings_list
        self._controller = controller
        self._last_main_page_index = 0
        self._cached_data_range = 1
        self._current_theme_mode = "light"

        self._setup_layout_structure()  # [FIX] Setup lại layout
        self._setup_ui()
        self._connect_signals()

    def _setup_layout_structure(self):
        """
        [FIX 4] Tái cấu trúc layout để đảm bảo Settings luôn nằm đáy và không bị che.
        """
        # Nếu container chưa có layout, tạo mới. Nếu có, lấy lại dùng.
        if not self._frame.layout():
            layout = QVBoxLayout(self._frame)
            self._frame.setLayout(layout)
        else:
            layout = self._frame.layout()

        # Cấu hình Layout: Padding 0, Spacing 0
        layout.setContentsMargins(0, 0, 0, 10)  # [QUAN TRỌNG] Padding Bottom 10px để Settings cách đáy
        layout.setSpacing(0)

        # Đảm bảo nav_list chiếm hết khoảng trống, settings_list chỉ lấy đủ phần nó cần
        # Lưu ý: Trong Qt Designer, nav_list và settings_list có thể đã được add vào layout.
        # Ở đây ta chỉ chỉnh lại Policy.

        # Nav List: Expand để đẩy Settings xuống
        # Settings List: Fixed Height (đủ cho 1 item = 40px + margin)
        self._settings_list.setFixedHeight(60)  # 40px item + margin
        self._settings_list.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

    def _setup_ui(self):
        """Initialize list widgets."""
        self._nav_list.clear()
        self._settings_list.clear()

        # Tắt ScrollBar
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

        self._nav_list.setCurrentRow(0)

    def _connect_signals(self):
        self._nav_list.itemClicked.connect(self._on_nav_clicked)
        self._settings_list.itemClicked.connect(self._on_settings_clicked)

    def render(self, state: dict):
        """Update sidebar state based on store."""
        is_expanded = select_left_menu_expanded(state)
        current_page = select_current_page(state)
        self._cached_data_range = select_data_range_days(state)

        new_theme = state.get("theme", "light")
        if new_theme != self._current_theme_mode:
            self._current_theme_mode = new_theme
            self._update_icons(is_expanded)

        # Update Width
        width = UIConstants.MENU_EXPANDED_WIDTH if is_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        self._frame.setFixedWidth(width)

        # Update CSS Property
        collapsed_str = "true" if not is_expanded else "false"
        if self._nav_list.property("collapsed") != collapsed_str:
            self._nav_list.setProperty("collapsed", collapsed_str)
            self._settings_list.setProperty("collapsed", collapsed_str)

            # Repolish
            self._nav_list.style().unpolish(self._nav_list)
            self._nav_list.style().polish(self._nav_list)
            self._settings_list.style().unpolish(self._settings_list)
            self._settings_list.style().polish(self._settings_list)

        self._update_icons(is_expanded)
        self._sync_selection(current_page)

    def _update_icons(self, is_expanded: bool):
        for i in range(self._nav_list.count()):
            item = self._nav_list.item(i)
            page_id = item.data(Qt.UserRole)
            icon_key = ":/icon/dashboard.svg" if "daboard" in page_id else ":/icon/orders.svg"
            item.setIcon(QIcon(theme_manager.get_icon_path(icon_key)))

        item = self._settings_list.item(0)
        if item:
            item.setIcon(QIcon(theme_manager.get_icon_path(":/icon/settings.svg")))

    def _sync_selection(self, page_id: str):
        if page_id == "settings_page":
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
        # ... (Giữ nguyên logic menu popup như cũ) ...
        is_dark = self._current_theme_mode == "dark"
        bg_color = "#2D2D2D" if is_dark else "#FFFFFF"
        text_color = "#FFFFFF" if is_dark else "#000000"
        border_color = "#3E3E3E" if is_dark else "#D3D3D3"
        hover_bg = "#3E3E3E" if is_dark else "#F0F0F0"

        menu = QMenu(self._settings_list)
        menu.setStyleSheet(
            f"""
            QMenu {{ background-color: {bg_color}; border: 1px solid {border_color}; padding: 4px; border-radius: 6px; }}
            QMenu::item {{ padding: 6px 24px; font-size: 13px; color: {text_color}; border-radius: 4px; }}
            QMenu::item:selected {{ background-color: {hover_bg}; }}
            QMenu::item:checked {{ font-weight: bold; color: #0078D4; }}
            """
        )

        options = [("Last 1 Day", 1), ("Last 1 Week", 7), ("Last 1 Month", 30), ("Last 3 Months", 90)]
        current_days = self._cached_data_range

        for text, days in options:
            action = QAction(text, menu)
            action.setCheckable(True)
            if days == current_days:
                action.setChecked(True)
            action.triggered.connect(lambda chk, d=days: self._controller.handle_data_range_change(d))
            menu.addAction(action)

        rect = self._settings_list.visualItemRect(item)
        global_pos = self._settings_list.mapToGlobal(rect.topRight())
        menu.exec(global_pos + QPoint(5, -5))
        self._settings_list.clearSelection()

    def set_data_range(self, days: int):
        self._cached_data_range = days
