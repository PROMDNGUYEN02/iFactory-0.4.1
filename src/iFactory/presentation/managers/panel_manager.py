# File: src/iFactory/presentation/managers/panel_manager.py
"""
Panel Manager - Manages settings and theme panels.
"""
from __future__ import annotations
import logging
from typing import Callable, Optional

from PySide6.QtCore import QTimer, QPoint, QRect
from PySide6.QtWidgets import QWidget, QFrame

from iFactory.ui.widgets.constants import Icons

logger = logging.getLogger(__name__)


def _safe_import(module_path: str, symbol: str, fallback=None):
    """Safely import a symbol from a module path."""
    try:
        module = __import__(module_path, fromlist=[symbol])
        return getattr(module, symbol, fallback)
    except Exception as e:
        logger.warning(f"Import {symbol} from {module_path} failed: {e}")
        return fallback


MenuDelegate = _safe_import("iFactory.ui.widgets.menu_widgets", "MenuDelegate")
ClickCatcher = _safe_import("iFactory.ui.widgets.panel_widgets", "ClickCatcher")
SettingsRootPanel = _safe_import(
    "iFactory.ui.widgets.panel_widgets", "SettingsRootPanel"
)
ThemeSubPanel = _safe_import("iFactory.ui.widgets.panel_widgets", "ThemeSubPanel")


class FallbackClickCatcher(QWidget):
    """Fallback click catcher if import fails."""

    clicked = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self.hide()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.pos())
            event.accept()


class FallbackPanel(QFrame):
    """Fallback panel if import fails."""

    def __init__(self, parent=None, icons=None):
        super().__init__(parent)
        self.setFixedWidth(220)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.btn_theme = QPushButton("Theme")
        self.btn_theme.set_click_callback = lambda cb: self.btn_theme.clicked.connect(
            cb
        )
        self.btn_info = QPushButton("Info")
        self.btn_info.set_click_callback = lambda cb: self.btn_info.clicked.connect(cb)
        layout.addWidget(self.btn_theme)
        layout.addWidget(self.btn_info)
        self.hide()

    def update_icons(self):
        pass


class FallbackThemePanel(QFrame):
    """Fallback theme panel if import fails."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedWidth(100)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        self.btn_light = QPushButton("Light")
        self.btn_light.set_click_callback = lambda cb: self.btn_light.clicked.connect(
            cb
        )
        self.btn_dark = QPushButton("Dark")
        self.btn_dark.set_click_callback = lambda cb: self.btn_dark.clicked.connect(cb)
        layout.addWidget(self.btn_light)
        layout.addWidget(self.btn_dark)
        self.hide()


class PanelManager:
    """Manages settings and theme panels."""

    __slots__ = (
        "_container",
        "_icons",
        "_constants",
        "_click_catcher",
        "_settings_panel",
        "_theme_panel",
        "_theme_hide_timer",
        "_position_timer",
        "_position_cb_connected",
        "_settings_rect_fn",
        "_left_menu_rect_fn",
    )

    def __init__(self, container: QWidget, icon_manager: Any, constants: Any):
        self._container = container
        self._icons = icon_manager
        self._constants = constants

        self._click_catcher = (
            ClickCatcher(container) if ClickCatcher else FallbackClickCatcher(container)
        )
        self._settings_panel = (
            SettingsRootPanel(container, icon_manager)
            if SettingsRootPanel
            else FallbackPanel(container, icon_manager)
        )
        self._theme_panel = (
            ThemeSubPanel(container) if ThemeSubPanel else FallbackThemePanel(container)
        )

        self._theme_hide_timer = QTimer()
        self._theme_hide_timer.setSingleShot(True)
        self._theme_hide_timer.setInterval(self._constants.TIMER_THEME_HIDE)
        self._theme_hide_timer.timeout.connect(self._check_hide_theme)

        self._position_timer = QTimer()
        self._position_timer.setSingleShot(True)
        self._position_timer.setInterval(self._constants.TIMER_POSITION_UPDATE)
        self._position_cb_connected = False

        self._settings_rect_fn: Optional[Callable[[], QRect]] = None
        self._left_menu_rect_fn: Optional[Callable[[], QRect]] = None

        self._click_catcher.hide()
        self._settings_panel.hide()
        self._theme_panel.hide()

    @property
    def settings_panel(self):
        return self._settings_panel

    @property
    def theme_panel(self):
        return self._theme_panel

    @property
    def click_catcher(self):
        return self._click_catcher

    def set_rect_providers(
        self, settings_rect: Callable[[], QRect], left_menu_rect: Callable[[], QRect]
    ) -> None:
        """Set rectangle providers for positioning."""
        self._settings_rect_fn = settings_rect
        self._left_menu_rect_fn = left_menu_rect

    def set_position_callback(self, callback: Callable[[], None]) -> None:
        """Set position update callback."""
        if self._position_cb_connected:
            try:
                self._position_timer.timeout.disconnect()
            except (TypeError, RuntimeError):
                pass
        self._position_timer.timeout.connect(callback)
        self._position_cb_connected = True

    def toggle_settings(self) -> None:
        """Toggle settings panel visibility."""
        if self._settings_panel.isVisible() or self._theme_panel.isVisible():
            self.hide_all()
        else:
            self.show_settings()

    def show_settings(self) -> None:
        """Show settings panel."""
        self._settings_panel.show()
        self._settings_panel.raise_()
        self._theme_panel.hide()
        self._show_click_catcher()
        self._schedule_position_update()

    def show_theme_panel(self) -> None:
        """Show theme panel."""
        self._theme_hide_timer.stop()
        if not self._theme_panel.isVisible():
            self._theme_panel.show()
            self._theme_panel.raise_()
            self._schedule_position_update()

    def hide_all(self) -> None:
        """Hide all panels."""
        self._theme_hide_timer.stop()
        self._theme_panel.hide()
        self._settings_panel.hide()
        self._click_catcher.hide()

    def any_visible(self) -> bool:
        """Check if any panel is visible."""
        return self._settings_panel.isVisible() or self._theme_panel.isVisible()

    def _show_click_catcher(self) -> None:
        """Show click catcher behind panels."""
        self._click_catcher.setGeometry(self._container.rect())
        self._click_catcher.lower()
        self._click_catcher.show()
        self._settings_panel.raise_()
        self._theme_panel.raise_()

    def handle_click_outside(self, pos: QPoint) -> bool:
        """Handle click outside panels."""
        if self._settings_rect_fn:
            if self._settings_rect_fn().contains(pos):
                self.hide_all()
                self.toggle_settings()
                return True
        for panel in (self._settings_panel, self._theme_panel):
            if panel.isVisible() and panel.geometry().contains(pos):
                return False
        self.hide_all()
        return True

    def _schedule_position_update(self) -> None:
        """Schedule position update."""
        if not self._position_timer.isActive():
            self._position_timer.start()

    def update_positions(self) -> None:
        """Update panel positions."""
        if not self.any_visible():
            return
        if not self._left_menu_rect_fn or not self._settings_rect_fn:
            return

        container = self._container.rect()
        left_menu = self._left_menu_rect_fn()
        settings_item = self._settings_rect_fn()
        margin = 6

        x_start = left_menu.right() + 1 + margin
        avail_w = container.width() - x_start - margin
        if avail_w <= 0:
            self.hide_all()
            return

        sp = self._settings_panel
        w = max(1, min(sp.sizeHint().width(), avail_w))
        h = max(1, min(sp.sizeHint().height(), container.height() - 2 * margin))
        y = max(
            margin,
            min(
                settings_item.top() if not settings_item.isNull() else margin,
                container.height() - h - margin,
            ),
        )

        x = (
            x_start
            if x_start + w <= container.width() - margin
            else max(x_start, container.width() - w - margin)
        )

        sp.setGeometry(x, y, w, h)

        if self._theme_panel.isVisible():
            self._position_theme_panel(container, margin)

    def _position_theme_panel(self, container: QRect, margin: int) -> None:
        """Position theme panel next to settings."""
        sg = self._settings_panel.geometry()
        tp = self._theme_panel

        (hint_w, hint_h) = (tp.sizeHint().width(), tp.sizeHint().height())
        x_right = sg.right() + 1 + margin
        avail_r = container.width() - x_right - margin

        if avail_r > 0:
            w = max(1, min(hint_w, avail_r))
            h = max(1, min(hint_h, container.height() - 2 * margin))
            if hasattr(self._settings_panel, "btn_theme"):
                btn_y = self._settings_panel.btn_theme.mapTo(
                    self._container, QPoint(0, 0)
                ).y()
            else:
                btn_y = margin
            y = max(margin, min(btn_y, container.height() - h - margin))
            tp.setGeometry(x_right, y, w, h)
        else:
            tp.hide()

    def _check_hide_theme(self) -> None:
        """Check if theme panel should hide."""
        if not self._theme_panel.isVisible():
            return
        cursor = self._container.cursor().pos()
        widgets_to_check = [
            (
                self._settings_panel.btn_theme
                if hasattr(self._settings_panel, "btn_theme")
                else None
            ),
            self._theme_panel,
        ]
        if hasattr(self._theme_panel, "btn_light"):
            widgets_to_check.append(self._theme_panel.btn_light)
        if hasattr(self._theme_panel, "btn_dark"):
            widgets_to_check.append(self._theme_panel.btn_dark)

        for w in widgets_to_check:
            if w and w.isVisible():
                r = QRect(w.mapToGlobal(QPoint(0, 0)), w.size())
                if r.contains(cursor):
                    return
        self._theme_panel.hide()

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._theme_hide_timer.stop()
        self._position_timer.stop()
