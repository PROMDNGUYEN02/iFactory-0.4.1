# File: presentation/views/shell/sidebar.py
"""
Sidebar View - MVVM Architecture.

OPTIMIZED:
1. Batch button updates on theme change
2. Skip redundant updates via state comparison
3. Cached styles per theme
4. Proper widget lifecycle
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union, Callable

from PySide6.QtCore import Qt, QSize, QPoint, Slot, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPainterPath, QBrush
from PySide6.QtWidgets import (
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QWidget,
    QListWidget,
    QMenu,
    QGraphicsDropShadowEffect,
)

from ...constants.layout import Layout
from ...resources.icons import Icons

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


# =============================================================================
# State Models
# =============================================================================


@dataclass
class SidebarState:
    """Sidebar state for comparison."""

    is_expanded: bool
    current_page: str
    theme: str
    data_range_days: int = 1


@dataclass
class NavButtonState:
    """Nav button state."""

    is_active: bool
    is_expanded: bool
    is_hovered: bool
    theme: str


# =============================================================================
# Navigation Button Base
# =============================================================================


class NavButtonBase(QWidget):
    """
    Base class for navigation buttons.

    Features:
    - Theme-aware icon and text
    - Hover and active states
    - Smooth visual feedback
    """

    clicked = Signal()

    def __init__(
        self,
        icon: Union[Icons, str],
        text: str,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._icon = icon
        self._text = text
        self._theme_service = theme_service

        # State
        self._is_active = False
        self._is_expanded = False
        self._is_hovered = False
        self._current_theme = theme_service.current_theme

        # Setup
        self.setFixedHeight(44)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAttribute(Qt.WidgetAttribute.WA_Hover)

        self._setup_ui()
        self._theme_service.themeChanged.connect(self._on_theme_changed)

    def _setup_ui(self) -> None:
        """Setup button UI elements."""
        self._main_layout = QHBoxLayout(self)
        self._main_layout.setContentsMargins(0, 4, 0, 4)
        self._main_layout.setSpacing(12)

        # Icon container
        self._icon_container = QWidget()
        self._icon_container.setFixedSize(36, 36)
        icon_layout = QHBoxLayout(self._icon_container)
        icon_layout.setContentsMargins(0, 0, 0, 0)
        icon_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(22, 22)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_label.setScaledContents(True)
        icon_layout.addWidget(self._icon_label)

        self._main_layout.addWidget(self._icon_container)

        # Text label
        self._text_label = QLabel(self._text)
        self._text_label.setFont(QFont("Segoe UI", 10))
        self._text_label.setVisible(False)
        self._main_layout.addWidget(self._text_label, 1)

        self.setToolTip(self._text)
        self._update_icon()
        self._apply_style()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme == self._current_theme:
            return

        self._current_theme = theme
        self._update_icon()
        self._apply_style()
        self.update()

    def _update_icon(self) -> None:
        """Update icon pixmap."""
        pixmap = self._theme_service.get_pixmap(self._icon, QSize(20, 20))
        self._icon_label.setPixmap(pixmap)

    def _apply_style(self) -> None:
        """Apply current style based on state."""
        tokens = self._theme_service.tokens

        if self._is_active:
            text_color = tokens.primary
            font_weight = tokens.font_weight_semibold
        elif self._is_hovered:
            text_color = tokens.text_primary
            font_weight = tokens.font_weight_medium
        else:
            text_color = tokens.text_muted
            font_weight = tokens.font_weight_medium

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

    def set_expanded(self, expanded: bool) -> None:
        """Set expanded state."""
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
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        """Custom paint for background effects."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tokens = self._theme_service.tokens
        margin = 6 if self._is_expanded else 4
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        if self._is_active:
            # Active background
            bg_color = QColor(tokens.primary)
            bg_color.setAlphaF(0.15)
            painter.fillPath(path, QBrush(bg_color))

            # Active indicator line
            indicator = QPainterPath()
            indicator.addRoundedRect(margin, rect.top() + 8, 3, rect.height() - 16, 1.5, 1.5)
            painter.fillPath(indicator, QBrush(QColor(tokens.primary)))

        elif self._is_hovered:
            # Hover background
            bg_color = QColor(tokens.interactive_hover)
            bg_color.setAlphaF(0.5)
            painter.fillPath(path, QBrush(bg_color))


# =============================================================================
# Modern Navigation Button
# =============================================================================


class ModernNavButton(NavButtonBase):
    """Navigation button with page routing."""

    def __init__(
        self,
        icon: Union[Icons, str],
        text: str,
        page_id: str,
        on_click: Callable[[str], None],
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        self._page_id = page_id
        self._on_click_handler = on_click
        super().__init__(icon, text, theme_service, parent)
        self.clicked.connect(self._handle_click)

    def _handle_click(self) -> None:
        """Handle button click."""
        self._on_click_handler(self._page_id)

    def set_active(self, active: bool) -> None:
        """Set active state."""
        if self._is_active == active:
            return

        self._is_active = active
        self._apply_style()
        self.update()

    @property
    def page_id(self) -> str:
        return self._page_id


# =============================================================================
# Settings Button
# =============================================================================


class SettingsButton(NavButtonBase):
    """Settings button that opens the settings menu."""

    def __init__(
        self,
        icon: Union[Icons, str],
        text: str,
        shell_vm: "ShellViewModel",
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        self._shell_vm = shell_vm
        self._current_range = 1
        super().__init__(icon, text, theme_service, parent)
        self.clicked.connect(self._show_menu)

    def set_current_range(self, days: int) -> None:
        """Update current data range."""
        self._current_range = days

    def _show_menu(self) -> None:
        """Show settings menu."""
        menu = SettingsMenu(
            shell_vm=self._shell_vm,
            current_range=self._current_range,
            theme_service=self._theme_service,
            parent=self,
        )

        menu.adjustSize()
        menu_height = menu.sizeHint().height()

        btn_global_pos = self.mapToGlobal(self.rect().topRight())
        sidebar_width = Layout.SIDEBAR_EXPANDED_WIDTH if self._is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH

        menu_x = self.mapToGlobal(QPoint(0, 0)).x() + sidebar_width + 8
        menu_y = btn_global_pos.y() - menu_height + self.height()

        if menu_y < 10:
            menu_y = btn_global_pos.y()

        menu.exec(QPoint(menu_x, menu_y))


# =============================================================================
# Settings Menu
# =============================================================================


class SettingsMenu(QMenu):
    """Professional settings menu with themed styling."""

    DATE_RANGE_OPTIONS: List[tuple] = [
        ("Today", 1),
        ("Last 7 Days", 7),
        ("Last 30 Days", 30),
        ("Last 3 Months", 90),
        ("Last 6 Months", 180),
        ("Last Year", 365),
    ]

    def __init__(
        self,
        shell_vm: "ShellViewModel",
        current_range: int,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._shell_vm = shell_vm
        self._current_range = current_range
        self._theme_service = theme_service

        self._setup_menu()

    def _setup_menu(self) -> None:
        """Setup menu styling and items."""
        tokens = self._theme_service.tokens
        is_dark = self._theme_service.is_dark

        self.setStyleSheet(
            f"""
            QMenu {{
                background-color: {tokens.surface_panel};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_lg};
                padding: {tokens.space_2} {tokens.space_1};
                min-width: 220px;
            }}
            QMenu::item {{
                background-color: transparent;
                color: {tokens.text_primary};
                padding: {tokens.space_2} {tokens.space_4};
                margin: 2px {tokens.space_1};
                border-radius: {tokens.radius_md};
                font-size: {tokens.font_size_base};
            }}
            QMenu::item:selected {{
                background-color: {tokens.interactive_hover};
            }}
            QMenu::item:disabled {{
                color: {tokens.text_muted};
                font-weight: {tokens.font_weight_bold};
                font-size: {tokens.font_size_xs};
            }}
            QMenu::separator {{
                height: 1px;
                background: {tokens.border_default};
                margin: {tokens.space_2} {tokens.space_3};
            }}
        """
        )

        # Shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 100 if is_dark else 50))
        self.setGraphicsEffect(shadow)

        self._build_menu_items()

    def _build_menu_items(self) -> None:
        """Build menu items."""
        # Data Range Section
        header = self.addAction("DATA RANGE")
        header.setEnabled(False)

        for label, days in self.DATE_RANGE_OPTIONS:
            is_selected = self._current_range == days
            display_label = f"  ✓ {label}" if is_selected else f"    {label}"
            action = self.addAction(display_label)
            action.triggered.connect(lambda checked, d=days: self._on_range_selected(d))

        self.addSeparator()

        # Appearance Section
        appearance_header = self.addAction("APPEARANCE")
        appearance_header.setEnabled(False)

        if self._theme_service.is_dark:
            theme_action = self.addAction("  ☀️ Switch to Light Mode")
        else:
            theme_action = self.addAction("  🌙 Switch to Dark Mode")

        theme_action.triggered.connect(self._shell_vm.toggle_theme)

        self.addSeparator()

        # About Section
        info_header = self.addAction("ABOUT")
        info_header.setEnabled(False)

        version_action = self.addAction("  ℹ️ Version 1.0.0")
        version_action.setEnabled(False)

    def _on_range_selected(self, days: int) -> None:
        """Handle range selection."""
        self._current_range = days
        logger.debug(f"[SettingsMenu] Data range selected: {days} days")


# =============================================================================
# Sidebar View
# =============================================================================


class SidebarView:
    """
    Sidebar navigation view.

    Features:
    - Navigation buttons with page routing
    - Settings menu
    - Collapsible design
    - Theme-aware styling

    NOTE: No __slots__ - needed for Qt signal weak references
    """

    NAV_ITEMS: List[tuple] = [
        (Icons.electrode, "Electrode", "electrode_page"),
        (Icons.assembly, "Assembly", "assembly_page"),
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

        # State
        self._state = SidebarState(
            is_expanded=False,
            current_page="",
            theme=theme_service.current_theme,
        )

        # Components
        self._nav_buttons: List[ModernNavButton] = []
        self._settings_btn: Optional[SettingsButton] = None

        # Style cache
        self._style_cache: Dict[str, str] = {}

        # UI elements
        self._content: Optional[QWidget] = None
        self._content_layout: Optional[QVBoxLayout] = None
        self._divider: Optional[QFrame] = None

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
        if theme == self._state.theme:
            return

        self._state = SidebarState(
            is_expanded=self._state.is_expanded,
            current_page=self._state.current_page,
            theme=theme,
            data_range_days=self._state.data_range_days,
        )
        self._style_cache.clear()
        self._apply_styles()

    @Slot(bool)
    def _on_sidebar_changed(self, expanded: bool) -> None:
        """Handle sidebar expansion change."""
        if expanded == self._state.is_expanded:
            return

        self._state = SidebarState(
            is_expanded=expanded,
            current_page=self._state.current_page,
            theme=self._state.theme,
            data_range_days=self._state.data_range_days,
        )
        self._update_expansion()

    @Slot(str)
    def _on_page_changed(self, page: str) -> None:
        """Handle page change."""
        if page == self._state.current_page:
            return

        self._state = SidebarState(
            is_expanded=self._state.is_expanded,
            current_page=page,
            theme=self._state.theme,
            data_range_days=self._state.data_range_days,
        )
        self._update_active(page)

    def _setup_sidebar(self) -> None:
        """Setup sidebar UI."""
        if not self._container:
            return

        self._container.setFixedWidth(Layout.SIDEBAR_COLLAPSED_WIDTH)

        # Hide original list widgets
        if self._nav_list:
            self._nav_list.hide()
        if self._settings_list:
            self._settings_list.hide()

        # Clear existing layout
        existing_layout = self._container.layout()
        if existing_layout:
            while existing_layout.count():
                item = existing_layout.takeAt(0)
                widget = item.widget()
                if widget and widget not in [self._nav_list, self._settings_list]:
                    widget.deleteLater()
                elif widget:
                    widget.hide()

        # Create content widget
        self._content = QWidget()
        self._content_layout = QVBoxLayout(self._content)
        self._content_layout.setContentsMargins(4, 12, 4, 12)
        self._content_layout.setSpacing(4)

        # Navigation buttons
        for icon_enum, text, page_id in self.NAV_ITEMS:
            btn = ModernNavButton(icon_enum, text, page_id, self._on_nav_click, self._theme_service)
            self._nav_buttons.append(btn)
            self._content_layout.addWidget(btn)

        self._content_layout.addStretch()

        # Divider
        self._divider = QFrame()
        self._divider.setFixedHeight(1)
        self._divider.setVisible(False)
        self._content_layout.addWidget(self._divider)

        # Settings button
        self._settings_btn = SettingsButton(Icons.SETTINGS, "Settings", self._shell_vm, self._theme_service)
        self._content_layout.addWidget(self._settings_btn)

        existing_layout.addWidget(self._content)
        self._apply_styles()

    def _apply_styles(self) -> None:
        """Apply theme styles with caching."""
        tokens = self._theme_service.tokens

        cache_key = f"sidebar_{self._state.theme}"
        if cache_key not in self._style_cache:
            self._style_cache[
                cache_key
            ] = f"""
                QFrame#left_slide_menu_frame {{
                    background-color: {tokens.surface_panel};
                    border: none;
                    border-right: 1px solid {tokens.border_default};
                }}
            """

        self._container.setStyleSheet(self._style_cache[cache_key])

        if self._divider:
            divider_key = f"divider_{self._state.theme}"
            if divider_key not in self._style_cache:
                self._style_cache[divider_key] = f"background-color: {tokens.border_subtle}; margin: 4px 12px;"
            self._divider.setStyleSheet(self._style_cache[divider_key])

    def _on_nav_click(self, page_id: str) -> None:
        """Handle navigation click."""
        self._shell_vm.navigate_to(page_id)

    def _update_active(self, current_page: str) -> None:
        """Update active button state."""
        normalized = current_page.replace("daboard", "electrode")
        for btn in self._nav_buttons:
            btn_page = btn.page_id.replace("daboard", "electrode")
            btn.set_active(btn_page == normalized)

    def _update_expansion(self) -> None:
        """Update expansion state for all buttons."""
        expanded = self._state.is_expanded

        for btn in self._nav_buttons:
            btn.set_expanded(expanded)
        if self._settings_btn:
            self._settings_btn.set_expanded(expanded)

        if self._divider:
            self._divider.setVisible(expanded)

        if self._content_layout:
            if expanded:
                self._content_layout.setContentsMargins(6, 12, 6, 12)
            else:
                self._content_layout.setContentsMargins(4, 12, 4, 12)

        width = Layout.SIDEBAR_EXPANDED_WIDTH if expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

    # =========================================================================
    # Legacy Compatibility
    # =========================================================================

    def render(self, state: Dict[str, Any]) -> None:
        """Render sidebar based on state (legacy compatibility)."""
        from ...state.selectors import (
            select_sidebar_expanded,
            select_current_page,
            select_data_range_days,
        )

        is_expanded = select_sidebar_expanded(state)
        current_page = select_current_page(state)
        data_range = select_data_range_days(state)

        # Update expansion if changed
        if is_expanded != self._state.is_expanded:
            self._state = SidebarState(
                is_expanded=is_expanded,
                current_page=self._state.current_page,
                theme=self._state.theme,
                data_range_days=data_range,
            )
            self._update_expansion()

        # Update active page if changed
        if current_page != self._state.current_page:
            self._state = SidebarState(
                is_expanded=self._state.is_expanded,
                current_page=current_page,
                theme=self._state.theme,
                data_range_days=data_range,
            )
            self._update_active(current_page)

        # Update settings button range
        if self._settings_btn:
            self._settings_btn.set_current_range(data_range)

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def dispose(self) -> None:
        """Clean up resources."""
        self._style_cache.clear()

        # Disconnect signals safely
        try:
            self._shell_vm.themeChanged.disconnect(self._on_theme_changed)
            self._shell_vm.sidebarChanged.disconnect(self._on_sidebar_changed)
            self._shell_vm.pageChanged.disconnect(self._on_page_changed)
        except (RuntimeError, TypeError):
            pass


__all__ = [
    "SidebarView",
    "NavButtonBase",
    "ModernNavButton",
    "SettingsButton",
    "SettingsMenu",
]
