from __future__ import annotations

from typing import TYPE_CHECKING, Optional, List

from PySide6.QtCore import Qt, QSize, QPoint
from PySide6.QtGui import QIcon, QFont, QColor, QPainter, QPainterPath, QBrush, QPixmap
from PySide6.QtWidgets import QFrame, QVBoxLayout, QHBoxLayout, QLabel, QWidget, QListWidget, QMenu, QGraphicsDropShadowEffect
from PySide6.QtSvg import QSvgRenderer

from ...constants.layout import Layout
from ...resources.themes import get_theme_manager
from ...state.selectors import select_current_page, select_sidebar_expanded, select_theme, select_data_range_days

if TYPE_CHECKING:
    from ...controllers.shell_controller import ShellController


def create_colored_icon(icon_path: str, color: QColor, size: int = 16) -> QIcon:
    """Create a colored icon from SVG path."""
    renderer = QSvgRenderer(icon_path)

    if not renderer.isValid():
        # Fallback: try loading as regular icon
        return QIcon(icon_path)

    # Create pixmap with transparency
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.transparent)

    # Render SVG
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    # Apply color mask
    colored_pixmap = QPixmap(pixmap.size())
    colored_pixmap.fill(Qt.transparent)

    painter = QPainter(colored_pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setCompositionMode(QPainter.CompositionMode_Source)
    painter.drawPixmap(0, 0, pixmap)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(colored_pixmap.rect(), color)
    painter.end()

    return QIcon(colored_pixmap)


class ModernNavButton(QWidget):
    def __init__(self, icon_path: str, text: str, page_id: str, on_click: callable, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_path = icon_path
        self._text = text
        self._page_id = page_id
        self._on_click = on_click
        self._is_active = False
        self._is_hovered = False
        self._is_expanded = False
        self._theme_manager = get_theme_manager()

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
        margin = 6 if self._is_expanded else 4
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        path = QPainterPath()
        path.addRoundedRect(rect, 10, 10)

        if self._is_active:
            bg_color = QColor(59, 130, 246, 30) if is_dark else QColor(59, 130, 246, 25)
            painter.fillPath(path, QBrush(bg_color))

            indicator = QPainterPath()
            indicator.addRoundedRect(margin, rect.top() + 8, 3, rect.height() - 16, 1.5, 1.5)
            painter.fillPath(indicator, QBrush(QColor("#3B82F6")))

        elif self._is_hovered:
            bg_color = QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 8)
            painter.fillPath(path, QBrush(bg_color))

    @property
    def page_id(self) -> str:
        return self._page_id


class SettingsMenu(QMenu):
    """Professional settings menu with themed icons."""

    DATE_RANGE_OPTIONS = [
        ("Today", 1, "calendar_today"),
        ("Last 7 Days", 7, "calendar_week"),
        ("Last 30 Days", 30, "calendar_month"),
        ("Last 3 Months", 90, "calendar_range"),
        ("Last 6 Months", 180, "calendar_range"),
        ("Last Year", 365, "calendar_year"),
    ]

    # Inline SVG data for menu icons (more reliable than external files)
    ICON_SVG = {
        "calendar_today": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
                <circle cx="12" cy="15" r="2"/>
            </svg>
        """,
        "calendar_week": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
                <line x1="7" y1="14" x2="11" y2="14"/>
                <line x1="7" y1="18" x2="17" y2="18"/>
            </svg>
        """,
        "calendar_month": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
                <rect x="7" y="13" width="10" height="6" rx="1"/>
            </svg>
        """,
        "calendar_range": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
                <path d="M7 14h10M7 18h6"/>
            </svg>
        """,
        "calendar_year": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <rect x="3" y="4" width="18" height="18" rx="2" ry="2"/>
                <line x1="16" y1="2" x2="16" y2="6"/>
                <line x1="8" y1="2" x2="8" y2="6"/>
                <line x1="3" y1="10" x2="21" y2="10"/>
                <path d="M8 14v4M12 13v5M16 15v3"/>
            </svg>
        """,
        "sun": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="5"/>
                <line x1="12" y1="1" x2="12" y2="3"/>
                <line x1="12" y1="21" x2="12" y2="23"/>
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
                <line x1="1" y1="12" x2="3" y2="12"/>
                <line x1="21" y1="12" x2="23" y2="12"/>
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
        """,
        "moon": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
            </svg>
        """,
        "info": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
        """,
        "check": """
            <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" 
                 stroke="{color}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"/>
            </svg>
        """,
    }

    def __init__(self, controller: "ShellController", current_range: int, theme_manager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._controller = controller
        self._current_range = current_range
        self._theme_manager = theme_manager
        self._is_dark = theme_manager.is_dark

        # Icon colors based on theme
        self._icon_color = "#E2E8F0" if self._is_dark else "#475569"
        self._icon_color_active = "#60A5FA" if self._is_dark else "#2563EB"
        self._icon_color_disabled = "#64748B" if self._is_dark else "#94A3B8"

        self._setup_menu()

    def _create_icon_from_svg(self, svg_name: str, color: str, size: int = 18) -> QIcon:
        """Create QIcon from inline SVG with specified color."""
        svg_template = self.ICON_SVG.get(svg_name, "")
        if not svg_template:
            return QIcon()

        # Replace color placeholder
        svg_data = svg_template.format(color=color).strip().encode("utf-8")

        # Create renderer from SVG data
        renderer = QSvgRenderer(svg_data)

        if not renderer.isValid():
            return QIcon()

        # Render to pixmap
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        renderer.render(painter)
        painter.end()

        return QIcon(pixmap)

    def _setup_menu(self) -> None:
        # Menu styling
        if self._is_dark:
            self.setStyleSheet(self._get_dark_style())
        else:
            self.setStyleSheet(self._get_light_style())

        # Add shadow
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(32)
        shadow.setXOffset(0)
        shadow.setYOffset(8)
        shadow.setColor(QColor(0, 0, 0, 100 if self._is_dark else 50))
        self.setGraphicsEffect(shadow)

        self._build_menu_items()

    def _get_dark_style(self) -> str:
        return """
            QMenu {
                background-color: #1E293B;
                border: 1px solid rgba(71, 85, 105, 0.8);
                border-radius: 12px;
                padding: 8px 6px;
                min-width: 220px;
            }
            QMenu::item {
                background-color: transparent;
                color: #CBD5E1;
                padding: 10px 16px 10px 14px;
                margin: 2px 6px;
                border-radius: 8px;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }
            QMenu::item:selected {
                background-color: rgba(71, 85, 105, 0.6);
                color: #F1F5F9;
            }
            QMenu::item:disabled {
                color: #64748B;
                background: transparent;
                padding: 8px 14px 6px 14px;
                font-weight: 700;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(71, 85, 105, 0.6);
                margin: 8px 12px;
            }
            QMenu::icon {
                padding-left: 6px;
            }
        """

    def _get_light_style(self) -> str:
        return """
            QMenu {
                background-color: #FFFFFF;
                border: 1px solid rgba(203, 213, 225, 0.9);
                border-radius: 12px;
                padding: 8px 6px;
                min-width: 220px;
            }
            QMenu::item {
                background-color: transparent;
                color: #475569;
                padding: 10px 16px 10px 14px;
                margin: 2px 6px;
                border-radius: 8px;
                font-size: 13px;
                font-family: 'Segoe UI', sans-serif;
            }
            QMenu::item:selected {
                background-color: rgba(241, 245, 249, 0.95);
                color: #1E293B;
            }
            QMenu::item:disabled {
                color: #94A3B8;
                background: transparent;
                padding: 8px 14px 6px 14px;
                font-weight: 700;
                font-size: 10px;
                letter-spacing: 1px;
            }
            QMenu::separator {
                height: 1px;
                background: rgba(203, 213, 225, 0.8);
                margin: 8px 12px;
            }
            QMenu::icon {
                padding-left: 6px;
            }
        """

    def _build_menu_items(self) -> None:
        # Data Range Section Header
        header = self.addAction("DATA RANGE")
        header.setEnabled(False)

        # Date range options with themed icons
        for label, days, icon_name in self.DATE_RANGE_OPTIONS:
            is_selected = self._current_range == days

            # Use active color for selected item
            icon_color = self._icon_color_active if is_selected else self._icon_color
            icon = self._create_icon_from_svg(icon_name, icon_color)

            # Add checkmark for selected item
            display_label = f"  {label}" if not is_selected else f"  {label}"
            action = self.addAction(icon, display_label)

            if is_selected:
                # Add checkmark icon to indicate selection
                action.setIcon(self._create_icon_from_svg("check", self._icon_color_active))

            action.triggered.connect(lambda checked, d=days: self._on_range_selected(d))

        self.addSeparator()

        # Appearance Section Header
        appearance_header = self.addAction("APPEARANCE")
        appearance_header.setEnabled(False)

        # Theme toggle with appropriate icon
        if self._is_dark:
            theme_icon = self._create_icon_from_svg("sun", self._icon_color)
            theme_action = self.addAction(theme_icon, "  Switch to Light Mode")
        else:
            theme_icon = self._create_icon_from_svg("moon", self._icon_color)
            theme_action = self.addAction(theme_icon, "  Switch to Dark Mode")

        theme_action.triggered.connect(self._controller.toggle_theme)

        self.addSeparator()

        # About Section Header
        info_header = self.addAction("ABOUT")
        info_header.setEnabled(False)

        # Version info with icon
        version_icon = self._create_icon_from_svg("info", self._icon_color_disabled)
        version_action = self.addAction(version_icon, "  Version 1.0.0")
        version_action.setEnabled(False)

    def _on_range_selected(self, days: int) -> None:
        self._current_range = days
        self._controller.set_data_range(days)


class SettingsButton(QWidget):
    def __init__(self, icon_path: str, text: str, controller: "ShellController", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icon_path = icon_path
        self._text = text
        self._controller = controller
        self._is_hovered = False
        self._is_expanded = False
        self._current_range = 1
        self._theme_manager = get_theme_manager()

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
        menu = SettingsMenu(controller=self._controller, current_range=self._current_range, theme_manager=self._theme_manager, parent=self)

        # Calculate menu size
        menu.adjustSize()
        menu_height = menu.sizeHint().height()

        # Get button position in global coordinates
        btn_global_pos = self.mapToGlobal(self.rect().topRight())

        # Position menu to the RIGHT of sidebar, ABOVE the button
        # Menu appears above to avoid covering status bar
        sidebar_width = Layout.SIDEBAR_EXPANDED_WIDTH if self._is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH

        menu_x = self.mapToGlobal(QPoint(0, 0)).x() + sidebar_width + 8
        menu_y = btn_global_pos.y() - menu_height + self.height()

        # Ensure menu doesn't go above the screen
        if menu_y < 10:
            # If not enough space above, show below
            menu_y = btn_global_pos.y()

        menu.exec(QPoint(menu_x, menu_y))

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        is_dark = self._theme_manager.is_dark
        margin = 6 if self._is_expanded else 4
        rect = self.rect().adjusted(margin, 2, -margin, -2)

        if self._is_hovered:
            path = QPainterPath()
            path.addRoundedRect(rect, 10, 10)
            bg_color = QColor(255, 255, 255, 15) if is_dark else QColor(0, 0, 0, 8)
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

        # Navigation buttons only (no MENU label)
        for icon_path, text, page_id in self.NAV_ITEMS:
            btn = ModernNavButton(icon_path, text, page_id, self._on_nav_click)
            self._nav_buttons.append(btn)
            self._content_layout.addWidget(btn)

        self._content_layout.addStretch()

        # Divider (hidden when collapsed)
        self._divider = QFrame()
        self._divider.setFixedHeight(1)
        self._divider.setVisible(False)
        self._content_layout.addWidget(self._divider)

        # Settings button
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

        divider_color = "rgba(100, 116, 139, 0.2)" if is_dark else "rgba(148, 163, 184, 0.2)"
        self._divider.setStyleSheet(f"background-color: {divider_color}; margin: 4px 12px;")

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

            self._divider.setVisible(is_expanded)

            if is_expanded:
                self._content_layout.setContentsMargins(6, 12, 6, 12)
            else:
                self._content_layout.setContentsMargins(4, 12, 4, 12)

        width = Layout.SIDEBAR_EXPANDED_WIDTH if is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        self._update_active(current_page)

        if self._settings_btn:
            self._settings_btn.set_current_range(data_range)


__all__ = ["SidebarView"]
