# File: presentation/views/shell/sidebar.py
"""
Sidebar View - MVVM Architecture.

Modern navigation sidebar with:
- Navigation buttons using Icons enum
- Settings menu
- Theme support via ThemeService
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from PySide6.QtCore import Qt, QSize, QPoint, Slot
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QListWidget, QMenu, QGraphicsDropShadowEffect

from ...constants.layout import Layout
from ...resources.icons import Icons
from ...state.selectors import select_current_page, select_sidebar_expanded, select_data_range_days

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


class ModernNavButton(QWidget):
    """Modern navigation button with hover and active states."""

    def __init__(
        self,
        icon: Union[Icons, str],  # Accept enum or legacy string
        text: str,
        page_id: str,
        on_click: callable,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self._page_id = page_id
        self._on_click = on_click
        self._theme_service = theme_service
        self._is_active = False
        self._is_hovered = False
        self._is_expanded = False

        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 4, 0, 4)
        self._main_layout.setSpacing(12)

        self._icon_container = QWidget()
        self._icon_container.setFixedSize(36, 36)
        icon_layout = QHBoxLayout(self._icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setScaledContents(True)
        icon_layout.addWidget(self._icon_label)

        self._main_layout.addWidget(self._icon_container)

        self._text_label = QLabel(self._text)
        self._text_label.setFont(QFont("Segoe UI", 10))
        self._text_label.setVisible(False)
        self._main_layout.addWidget(self._text_label, 1)

        self.setToolTip(self._text)

        self._update_icon()
        self._apply_style()

    def _update_icon(self) -> None:
        """Update icon using ThemeService (handles caching and theming)."""
        pixmap = self._theme_service.get_pixmap(self._icon, QSize(20, 20))
        self._icon_label.setPixmap(pixmap)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        if self._is_active:
            text_color = tokens.accent
            font_weight = "600"
        elif self._is_hovered:
            text_color = tokens.app_fg
            font_weight = "500"
        else:
            text_color = tokens.hint
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
        self._icon_container.setStyleSheet("background: transparent;")

    def set_active(self, active: bool) -> None:
        if self._is_active != active:
            self._is_active = active
            self._apply_style()
            self.update()

    def set_expanded(self, expanded: bool) -> None:
        if self._is_expanded == expanded:
            return

        self._is_expanded = expanded
        self._text_label.setVisible(expanded)

        if expanded:
            self._main_layout.setContentsMargins(10, 4, 10, 4)
            self.setToolTip("")
        else:
            self._main_layout.setContentsMargins(0, 4, 0, 4)
            self.setToolTip(self._text)

    def set_theme(self, theme: str) -> None:
        """Handle theme change - icons are automatically updated via cache invalidation."""
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

        tokens = self._theme_service.tokens
        margin = 6 if self._is_expanded else 4
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        if self._is_active:
            bg_color = QColor(tokens.accent)
            bg_color.setAlphaF(0.15)
            painter.fillPath(path, QBrush(bg_color))

            indicator = QPainterPath()
            indicator.addRoundedRect(margin, rect.top() + 8, 3, rect.height() - 16, 1.5, 1.5)
            painter.fillPath(indicator, QBrush(QColor(tokens.accent)))

        elif self._is_hovered:
            bg_color = QColor(tokens.hover)
            bg_color.setAlphaF(0.5)
            painter.fillPath(path, QBrush(bg_color))

    @property
    def page_id(self) -> str:
        return self._page_id


class SettingsButton(QWidget):
    """Settings button that opens the settings menu."""

    def __init__(
        self, icon: Union[Icons, str], text: str, shell_vm: "ShellViewModel", theme_service: "ThemeService", parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self._shell_vm = shell_vm
        self._theme_service = theme_service
        self._is_hovered = False
        self._is_expanded = False
        self._current_range = 1

        self.setFixedHeight(44)
        self.setCursor(Qt.PointingHandCursor)
        self.setAttribute(Qt.WA_Hover)

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 4, 0, 4)
        self._main_layout.setSpacing(12)

        self._icon_container = QWidget()
        self._icon_container.setFixedSize(36, 36)
        icon_layout = QHBoxLayout(self._icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignCenter)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        self._icon_label.setAlignment(Qt.AlignCenter)
        self._icon_label.setScaledContents(True)
        icon_layout.addWidget(self._icon_label)

        self._main_layout.addWidget(self._icon_container)

        self._text_label = QLabel(self._text)
        self._text_label.setFont(QFont("Segoe UI", 10))
        self._text_label.setVisible(False)
        self._main_layout.addWidget(self._text_label, 1)

        self.setToolTip(self._text)

        self._update_icon()
        self._apply_style()

    def _update_icon(self) -> None:
        """Update icon using ThemeService."""
        pixmap = self._theme_service.get_pixmap(self._icon, QSize(20, 20))
        self._icon_label.setPixmap(pixmap)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        if self._is_hovered:
            text_color = tokens.app_fg
        else:
            text_color = tokens.hint

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
        self._icon_container.setStyleSheet("background: transparent;")

    def set_expanded(self, expanded: bool) -> None:
        if self._is_expanded == expanded:
            return

        self._is_expanded = expanded
        self._text_label.setVisible(expanded)

        if expanded:
            self._main_layout.setContentsMargins(10, 4, 10, 4)
            self.setToolTip("")
        else:
            self._main_layout.setContentsMargins(0, 4, 0, 4)
            self.setToolTip(self._text)

    def set_theme(self, theme: str) -> None:
        """Handle theme change."""
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
            self._show_menu()
        super().mousePressEvent(event)

    def _show_menu(self) -> None:
        menu = SettingsMenu(shell_vm=self._shell_vm, current_range=self._current_range, theme_service=self._theme_service, parent=self)

        menu.adjustSize()
        menu_height = menu.sizeHint().height()

        btn_global_pos = self.mapToGlobal(self.rect().topRight())
        sidebar_width = Layout.SIDEBAR_EXPANDED_WIDTH if self._is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH

        menu_x = self.mapToGlobal(QPoint(0, 0)).x() + sidebar_width + 8
        menu_y = btn_global_pos.y() - menu_height + self.height()

        if menu_y < 10:
            menu_y = btn_global_pos.y()

        menu.exec(QPoint(menu_x, menu_y))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        tokens = self._theme_service.tokens
        margin = 6 if self._is_expanded else 4
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        if self._is_hovered:
            path = QPainterPath()
            path.addRoundedRect(rect, 10, 10)
            bg_color = QColor(tokens.hover)
            bg_color.setAlphaF(0.5)
            painter.fillPath(path, QBrush(bg_color))


class SettingsMenu(QMenu):
    """Professional settings menu with themed styling."""

    DATE_RANGE_OPTIONS = [
        ("Today", 1),
        ("Last 7 Days", 7),
        ("Last 30 Days", 30),
        ("Last 3 Months", 90),
        ("Last 6 Months", 180),
        ("Last Year", 365),
    ]

    def __init__(self, shell_vm: "ShellViewModel", current_range: int, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._shell_vm = shell_vm
        self._current_range = current_range
        self._theme_service = theme_service

        self._setup_menu()

    def _setup_menu(self) -> None:
        tokens = self._theme_service.tokens
        is_dark = self._theme_service.is_dark

        self.setStyleSheet(
            f"""
            QMenu {{
                background-color: {tokens.slide_bg};
                border: 1px solid {tokens.get_rgba("border", 0.8)};
                border-radius: 12px;
                padding: 8px 6px;
                min-width: 220px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {tokens.app_fg};
                padding: 10px 16px 10px 14px;
                margin: 2px 6px;
                border-radius: 8px;
                font-size: 13px;
            }}
            QMenu::item:selected {{
                background-color: {tokens.hover};
                color: {tokens.app_fg};
            }}
            QMenu::item:disabled {{
                color: {tokens.hint};
                font-weight: 700;
                font-size: 10px;
            }}
            QMenu::separator {{
                height: 1px;
                background: {tokens.get_rgba("border", 0.6)};
                margin: 8px 12px;
            }}
        """
        )

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 100 if is_dark else 50))
        self.setGraphicsEffect(shadow)

        self._build_menu_items()

    def _build_menu_items(self) -> None:
        header = self.addAction("DATA RANGE")
        header.setEnabled(False)

        for label, days in self.DATE_RANGE_OPTIONS:
            is_selected = self._current_range == days
            display_label = f"  ✓ {label}" if is_selected else f"    {label}"
            action = self.addAction(display_label)
            action.triggered.connect(lambda checked, d=days: self._on_range_selected(d))

        self.addSeparator()

        appearance_header = self.addAction("APPEARANCE")
        appearance_header.setEnabled(False)

        if self._theme_service.is_dark:
            theme_action = self.addAction("  ☀️ Switch to Light Mode")
        else:
            theme_action = self.addAction("  🌙 Switch to Dark Mode")

        theme_action.triggered.connect(self._shell_vm.toggle_theme)

        self.addSeparator()

        info_header = self.addAction("ABOUT")
        info_header.setEnabled(False)

        version_action = self.addAction("  ℹ️ Version 1.0.0")
        version_action.setEnabled(False)

    def _on_range_selected(self, days: int) -> None:
        self._current_range = days
        logger.info(f"[SettingsMenu] Data range selected: {days} days")


class SidebarView:
    """Sidebar navigation view using ThemeService and Icons enum."""

    # Use Icons enum instead of string paths
    NAV_ITEMS = [
        (Icons.DASHBOARD, "Dashboard", "dashboard_page"),
        (Icons.ORDERS, "Analytics", "orders_page"),
    ]

    def __init__(
        self,
        container: QFrame,
        nav_list: QListWidget,
        settings_list: QListWidget,
        shell_vm: "ShellViewModel",
        theme_service: "ThemeService",
    ):
        self._container = container
        self._nav_list = nav_list
        self._settings_list = settings_list
        self._shell_vm = shell_vm
        self._theme_service = theme_service

        self._is_expanded = False
        self._nav_buttons: List[ModernNavButton] = []
        self._settings_btn: Optional[SettingsButton] = None

        self._setup_sidebar()
        self._bind_viewmodel()

    def _bind_viewmodel(self) -> None:
        """Bind to ViewModel signals."""
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.sidebarChanged.connect(self._on_sidebar_changed)
        self._shell_vm.pageChanged.connect(self._on_page_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self._apply_styles()
        for btn in self._nav_buttons:
            btn.set_theme(theme)
        if self._settings_btn:
            self._settings_btn.set_theme(theme)

    @Slot(bool)
    def _on_sidebar_changed(self, expanded: bool) -> None:
        """Handle sidebar expansion change."""
        if expanded != self._is_expanded:
            self._is_expanded = expanded
            self._update_expansion()

    @Slot(str)
    def _on_page_changed(self, page: str) -> None:
        """Handle page change."""
        self._update_active(page)

    def _setup_sidebar(self) -> None:
        if not self._container:
            return

        self._container.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)

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
        self._content_layout.setContentsMargins(4, 12, 4, 12)
        self._content_layout.setSpacing(4)

        # Create nav buttons with Icons enum
        for icon_enum, text, page_id in self.NAV_ITEMS:
            btn = ModernNavButton(icon_enum, text, page_id, self._on_nav_click, self._theme_service)  # Pass enum directly
            self._nav_buttons.append(btn)
            self._content_layout.addWidget(btn)

        self._content_layout.addStretch()

        self._divider = QFrame()
        self._divider.setFixedHeight(1)
        self._divider.setVisible(False)
        self._content_layout.addWidget(self._divider)

        # Settings button with Icons enum
        self._settings_btn = SettingsButton(Icons.SETTINGS, "Settings", self._shell_vm, self._theme_service)  # Use enum
        self._content_layout.addWidget(self._settings_btn)

        existing_layout.addWidget(self._content)
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply theme styles using ThemeService."""
        tokens = self._theme_service.tokens

        self._container.setStyleSheet(
            f"""
            QFrame#left_slide_menu_frame {{
                background-color: {tokens.get_rgba("slide.bg", 0.98)};
                border: none;
                border-right: 1px solid {tokens.get_rgba("border", 0.5)};
            }}
        """
        )

        divider_color = tokens.get_rgba("border", 0.2)
        self._divider.setStyleSheet(f"background-color: {divider_color}; margin: 4px 12px;")

    def _on_nav_click(self, page_id: str) -> None:
        """Handle navigation button click."""
        self._shell_vm.navigate_to(page_id)

    def _update_active(self, current_page: str) -> None:
        """Update active button based on current page."""
        normalized = current_page.replace("daboard", "dashboard")
        for btn in self._nav_buttons:
            btn_page = btn.page_id.replace("daboard", "dashboard")
            btn.set_active(btn_page == normalized)

    def _update_expansion(self) -> None:
        """Update expansion state of all buttons."""
        for btn in self._nav_buttons:
            btn.set_expanded(self._is_expanded)
        if self._settings_btn:
            self._settings_btn.set_expanded(self._is_expanded)

        self._divider.setVisible(self._is_expanded)

        if self._is_expanded:
            self._content_layout.setContentsMargins(6, 12, 6, 12)
        else:
            self._content_layout.setContentsMargins(4, 12, 4, 12)

        width = Layout.SIDEBAR_EXPANDED_WIDTH if self._is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

    def render(self, state: Dict[str, Any]) -> None:
        """Render sidebar based on state (legacy compatibility)."""
        is_expanded = select_sidebar_expanded(state)
        current_page = select_current_page(state)
        data_range = select_data_range_days(state)

        if is_expanded != self._is_expanded:
            self._is_expanded = is_expanded
            self._update_expansion()

        self._update_active(current_page)

        if self._settings_btn:
            self._settings_btn.set_current_range(data_range)


__all__ = ["SidebarView"]
