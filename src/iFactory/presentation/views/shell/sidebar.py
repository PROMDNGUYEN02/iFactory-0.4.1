# File: presentation/views/shell/sidebar.py
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPainterPath, QBrush, QAction
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QListWidget, QMenu

from ...constants.layout import Layout
from ...resources.themes import get_theme_manager
from ...state.selectors import select_current_page, select_sidebar_expanded, select_theme, select_data_range_days

if TYPE_CHECKING:
    from ...controllers.shell_controller import ShellController


class ModernNavButton(QWidget):
    def __init__(self, icon_path: str, text: str, page_id: str, on_click: callable, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_path = icon_path
        self._text = text
        self._page_id = page_id
        self._on_click = on_click
        self._is_active = False
        self._is_hovered = False
        self._is_expanded = True
        self._theme_manager = get_theme_manager()

        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(8, 4, 8, 4)
        self._main_layout.setSpacing(12)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setScaledContents(True)
        self._main_layout.addWidget(self._icon_label)

        self._text_label = QLabel(self._text)
        self._text_label.setFont(QFont("Segoe UI", 10))
        self._main_layout.addWidget(self._text_label, 1)

        self._update_icon()
        self._apply_style()

    def _update_icon(self) -> None:
        icon_path = self._theme_manager.get_icon_path(self._icon_path)
        pixmap = QIcon(icon_path).pixmap(QSize(20, 20))
        self._icon_label.setPixmap(pixmap)

    def _apply_style(self) -> None:
        is_dark = self._theme_manager.is_dark

        if self._is_active:
            text_color = "#3B82F6"
            font_weight = "600"
        elif self._is_hovered:
            text_color = "#E2E8F0" if is_dark else "#334155"
            font_weight = "500"
        else:
            text_color = "#94A3B8" if is_dark else "#64748B"
            font_weight = "500"

        self._text_label.setStyleSheet(
            f"""
            QLabel {{
                color: {text_color};
                background: transparent;
                font-weight: {font_weight};
            }}
        """
        )

        self._icon_label.setStyleSheet("background: transparent;")

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self._apply_style()
            self.update()

    def set_expanded(self, expanded: bool) -> None:
        self._is_expanded = expanded
        self._text_label.setVisible(expanded)

        if expanded:
            self._main_layout.setContentsMargins(8, 4, 8, 4)
            self._main_layout.setDirection(QHBoxLayout.LeftToRight)
            self.setToolTip("")
        else:
            self._main_layout.setContentsMargins(0, 4, 0, 4)
            self._main_layout.setDirection(QHBoxLayout.LeftToRight)
            self.setToolTip(self._text)

    def set_theme(self, theme: str) -> None:
        self._update_icon()
        self._apply_style()
        self.update()

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._apply_style()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._apply_style()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._on_click(self._page_id)
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        is_dark = self._theme_manager.is_dark
        margin = 6 if self._is_expanded else 8
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        path = QPainterPath()
        path.addRoundedRect(rect, 8, 8)

        if self._is_active:
            bg_color = QColor(59, 130, 246, 25) if is_dark else QColor(59, 130, 246, 20)
            painter.fillPath(path, QBrush(bg_color))

            indicator = QPainterPath()
            indicator.addRoundedRect(margin, rect.top() + 6, 3, rect.height() - 12, 1.5, 1.5)
            painter.fillPath(indicator, QBrush(QColor("#3B82F6")))

        elif self._is_hovered:
            bg_color = QColor(255, 255, 255, 10) if is_dark else QColor(0, 0, 0, 5)
            painter.fillPath(path, QBrush(bg_color))

    @property
    def page_id(self) -> str:
        return self._page_id


class SettingsButton(QWidget):
    DATE_RANGE_OPTIONS = [
        ("1 Day", 1),
        ("1 Week", 7),
        ("1 Month", 30),
        ("3 Months", 90),
        ("6 Months", 180),
        ("1 Year", 365),
    ]

    def __init__(self, icon_path: str, text: str, controller: "ShellController", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_path = icon_path
        self._text = text
        self._controller = controller
        self._is_hovered = False
        self._is_expanded = True
        self._current_range = 1
        self._theme_manager = get_theme_manager()

        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(8, 4, 8, 4)
        self._main_layout.setSpacing(12)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(24, 24)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setScaledContents(True)
        self._main_layout.addWidget(self._icon_label)

        self._text_label = QLabel(self._text)
        self._text_label.setFont(QFont("Segoe UI", 10))
        self._main_layout.addWidget(self._text_label, 1)

        self._update_icon()
        self._apply_style()

    def _update_icon(self) -> None:
        icon_path = self._theme_manager.get_icon_path(self._icon_path)
        pixmap = QIcon(icon_path).pixmap(QSize(20, 20))
        self._icon_label.setPixmap(pixmap)

    def _apply_style(self) -> None:
        is_dark = self._theme_manager.is_dark

        if self._is_hovered:
            text_color = "#E2E8F0" if is_dark else "#334155"
        else:
            text_color = "#94A3B8" if is_dark else "#64748B"

        self._text_label.setStyleSheet(
            f"""
            QLabel {{
                color: {text_color};
                background: transparent;
                font-weight: 500;
            }}
        """
        )
        self._icon_label.setStyleSheet("background: transparent;")

    def set_expanded(self, expanded: bool) -> None:
        self._is_expanded = expanded
        self._text_label.setVisible(expanded)

        if expanded:
            self._main_layout.setContentsMargins(8, 4, 8, 4)
            self.setToolTip("")
        else:
            self._main_layout.setContentsMargins(0, 4, 0, 4)
            self.setToolTip(self._text)

    def set_theme(self, theme: str) -> None:
        self._update_icon()
        self._apply_style()
        self.update()

    def set_current_range(self, days: int) -> None:
        self._current_range = days

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._apply_style()
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._apply_style()
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._show_menu(event.globalPosition().toPoint())
        super().mousePressEvent(event)

    def _show_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        is_dark = self._theme_manager.is_dark

        if is_dark:
            menu.setStyleSheet(
                """
                QMenu {
                    background-color: #1E293B;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    background-color: transparent;
                    color: #E2E8F0;
                    padding: 8px 24px 8px 12px;
                    border-radius: 4px;
                    margin: 2px 4px;
                }
                QMenu::item:selected {
                    background-color: #334155;
                    color: #FFFFFF;
                }
                QMenu::item:checked {
                    background-color: rgba(59, 130, 246, 0.2);
                    color: #60A5FA;
                }
                QMenu::separator {
                    height: 1px;
                    background: #334155;
                    margin: 6px 8px;
                }
            """
            )
        else:
            menu.setStyleSheet(
                """
                QMenu {
                    background-color: #FFFFFF;
                    border: 1px solid #E2E8F0;
                    border-radius: 8px;
                    padding: 6px;
                }
                QMenu::item {
                    background-color: transparent;
                    color: #334155;
                    padding: 8px 24px 8px 12px;
                    border-radius: 4px;
                    margin: 2px 4px;
                }
                QMenu::item:selected {
                    background-color: #F1F5F9;
                    color: #1E293B;
                }
                QMenu::item:checked {
                    background-color: rgba(59, 130, 246, 0.1);
                    color: #2563EB;
                }
                QMenu::separator {
                    height: 1px;
                    background: #E2E8F0;
                    margin: 6px 8px;
                }
            """
            )

        header = menu.addAction("📅 Data Range")
        header.setEnabled(False)
        menu.addSeparator()

        for label, days in self.DATE_RANGE_OPTIONS:
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(self._current_range == days)
            action.triggered.connect(lambda checked, d=days: self._on_range_selected(d))

        menu.addSeparator()

        theme_action = menu.addAction("🌙 Dark Mode" if not is_dark else "☀️ Light Mode")
        theme_action.triggered.connect(self._controller.toggle_theme)

        menu.exec(pos)

    def _on_range_selected(self, days: int) -> None:
        self._current_range = days
        self._controller.set_data_range(days)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        is_dark = self._theme_manager.is_dark
        margin = 6 if self._is_expanded else 8
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        if self._is_hovered:
            path = QPainterPath()
            path.addRoundedRect(rect, 8, 8)
            bg_color = QColor(255, 255, 255, 10) if is_dark else QColor(0, 0, 0, 5)
            painter.fillPath(path, QBrush(bg_color))


class SidebarView:
    NAV_ITEMS = [
        (":/icon/dashboard.svg", "Dashboard", "dashboard_page"),
        (":/icon/orders.svg", "Analytics", "orders_page"),
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
        self._is_expanded = False
        self._nav_buttons: List[ModernNavButton] = []
        self._settings_btn: Optional[SettingsButton] = None

        self._setup_sidebar()

    def _setup_sidebar(self) -> None:
        if not self._container:
            return

        if self._nav_list:
            self._nav_list.hide()
        if self._settings_list:
            self._settings_list.hide()

        existing_layout = self._container.layout()
        if existing_layout:
            while existing_layout.count():
                item = existing_layout.takeAt(0)
                widget = item.widget()
                if widget and widget not in [self._nav_list, self._settings_list]:
                    widget.deleteLater()
                elif widget:
                    widget.hide()

        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(6, 16, 6, 12)
        self._content_layout.setSpacing(2)

        self._section_label = QLabel("MENU")
        self._section_label.setFont(QFont("Segoe UI", 8, QFont.Bold))
        self._section_label.setStyleSheet("color: #64748B; padding: 0 10px 8px 10px; background: transparent;")
        self._content_layout.addWidget(self._section_label)

        for icon_path, text, page_id in self.NAV_ITEMS:
            btn = ModernNavButton(icon_path, text, page_id, self._on_nav_click)
            self._nav_buttons.append(btn)
            self._content_layout.addWidget(btn)

        self._content_layout.addStretch()

        self._divider = QFrame()
        self._divider.setFixedHeight(1)
        self._divider.setStyleSheet("background-color: rgba(148, 163, 184, 0.15); margin: 6px 10px;")
        self._content_layout.addWidget(self._divider)

        self._settings_btn = SettingsButton(":/icon/settings.svg", "Settings", self._controller)
        self._content_layout.addWidget(self._settings_btn)

        existing_layout.addWidget(self._content)

        self._apply_styles()

    def _apply_styles(self) -> None:
        is_dark = self._current_theme == "dark"

        if is_dark:
            bg = "rgba(15, 23, 42, 0.98)"
            border = "rgba(51, 65, 85, 0.5)"
        else:
            bg = "rgba(248, 250, 252, 0.98)"
            border = "rgba(226, 232, 240, 0.5)"

        self._container.setStyleSheet(
            f"""
            QFrame#left_slide_menu_frame {{
                background-color: {bg};
                border: none;
                border-right: 1px solid {border};
            }}
        """
        )

        section_color = "#475569" if is_dark else "#94A3B8"
        self._section_label.setStyleSheet(
            f"""
            QLabel {{
                color: {section_color};
                padding: 0 10px 8px 10px;
                background: transparent;
                font-size: 9px;
                font-weight: 700;
                letter-spacing: 0.5px;
            }}
        """
        )

        divider_color = "rgba(100, 116, 139, 0.2)" if is_dark else "rgba(148, 163, 184, 0.2)"
        self._divider.setStyleSheet(f"background-color: {divider_color}; margin: 6px 10px;")

    def _on_nav_click(self, page_id: str) -> None:
        self._controller.navigate_to(page_id)

    def _update_active(self, current_page: str) -> None:
        normalized = current_page.replace("daboard", "dashboard")
        for btn in self._nav_buttons:
            btn_page = btn.page_id.replace("daboard", "dashboard")
            btn.set_active(btn_page == normalized)

    def render(self, state: dict) -> None:
        theme = select_theme(state)
        is_expanded = select_sidebar_expanded(state)
        current_page = select_current_page(state)
        data_range = select_data_range_days(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_styles()
            for btn in self._nav_buttons:
                btn.set_theme(theme)
            if self._settings_btn:
                self._settings_btn.set_theme(theme)

        if is_expanded != self._is_expanded:
            self._is_expanded = is_expanded
            for btn in self._nav_buttons:
                btn.set_expanded(is_expanded)
            if self._settings_btn:
                self._settings_btn.set_expanded(is_expanded)

            self._section_label.setVisible(is_expanded)
            self._divider.setVisible(is_expanded)

            if is_expanded:
                self._content_layout.setContentsMargins(6, 16, 6, 12)
            else:
                self._content_layout.setContentsMargins(4, 16, 4, 12)

        width = Layout.SIDEBAR_EXPANDED_WIDTH if is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        self._update_active(current_page)

        if self._settings_btn:
            self._settings_btn.set_current_range(data_range)


__all__ = ["SidebarView"]
