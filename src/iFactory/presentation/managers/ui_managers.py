"""
UI Managers - Animation, Menu, Panel, Shortcut, RightPanel managers.

This module consolidates several UI managers.
Note: In a stricter refactoring, each class would likely reside
in its own file to satisfy SRP (Single Responsibility Principle).
"""

from __future__ import annotations
import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import TYPE_CHECKING, Any, Callable, Optional
from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QRect,
    QSignalBlocker,
    Qt,
    QTimer,
    QVariantAnimation,
    Signal,
)
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QLayout,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
    QLabel,
    QPushButton,
    QDateEdit,
)
from iFactory.presentation.managers.widgets.constants import WindowConstants, Icons

logger = logging.getLogger(__name__)
if TYPE_CHECKING:
    from iFactory.presentation.managers import IconManager


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
        self.btn_theme.set_click_callback = lambda cb: self.btn_theme.clicked.connect(cb)
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
        self.btn_light.set_click_callback = lambda cb: self.btn_light.clicked.connect(cb)
        self.btn_dark = QPushButton("Dark")
        self.btn_dark.set_click_callback = lambda cb: self.btn_dark.clicked.connect(cb)
        layout.addWidget(self.btn_light)
        layout.addWidget(self.btn_dark)
        self.hide()


def _safe_import(module_path: str, symbol: str, fallback=None):
    """Safely import a symbol from a module path."""
    try:
        module = __import__(module_path, fromlist=[symbol])
        return getattr(module, symbol, fallback)
    except Exception as e:
        logger.warning(f"Import {symbol} from {module_path} failed: {e}")
        return fallback


MenuDelegate = _safe_import("iFactory.presentation.managers.widgets.menu_widgets", "MenuDelegate")
ClickCatcher = _safe_import("iFactory.presentation.managers.widgets.panel_widgets", "ClickCatcher")
SettingsRootPanel = _safe_import("iFactory.presentation.managers.widgets.panel_widgets", "SettingsRootPanel")
ThemeSubPanel = _safe_import("iFactory.presentation.managers.widgets.panel_widgets", "ThemeSubPanel")
RightSlideMenuWidget = _safe_import("iFactory.presentation.managers.widgets.right_slide_menu", "RightSlideMenuWidget")
RightEdgeHoverZone = _safe_import("iFactory.presentation.managers.widgets.right_panel_components", "RightEdgeHoverZone")
RightMenuToggleButton = _safe_import("iFactory.presentation.managers.widgets.right_panel_components", "RightMenuToggleButton")


class AnimationTarget(Enum):
    """Animation target identifier."""

    LEFT_MENU = auto()
    RIGHT_PANEL = auto()


class AnimationManager:
    """Manages smooth animations for UI elements."""

    __slots__ = (
        "_constants",
        "_duration",
        "_left_group",
        "_left_min",
        "_left_max",
        "_right_group",
        "_right_min",
        "_right_max",
        "_left_min_cb",
        "_left_max_cb",
        "_left_done_cb",
        "_right_min_cb",
        "_right_max_cb",
        "_right_done_cb",
    )

    def __init__(
        self,
        constants: Optional[WindowConstants] = None,
        duration: Optional[int] = None,
    ):
        self._constants = constants or WindowConstants()
        self._duration = duration or self._constants.ANIMATION_DURATION
        self._left_group = QParallelAnimationGroup()
        self._left_min = self._create_animation()
        self._left_max = self._create_animation()
        self._left_group.addAnimation(self._left_min)
        self._left_group.addAnimation(self._left_max)
        self._right_group = QParallelAnimationGroup()
        self._right_min = self._create_animation()
        self._right_max = self._create_animation()
        self._right_group.addAnimation(self._right_min)
        self._right_group.addAnimation(self._right_max)
        self._left_min_cb: Optional[Callable[[int], None]] = None
        self._left_max_cb: Optional[Callable[[int], None]] = None
        self._left_done_cb: Optional[Callable[[], None]] = None
        self._right_min_cb: Optional[Callable[[int], None]] = None
        self._right_max_cb: Optional[Callable[[int], None]] = None
        self._right_done_cb: Optional[Callable[[], None]] = None
        self._left_min.valueChanged.connect(lambda v: self._left_min_cb and self._left_min_cb(v))
        self._left_max.valueChanged.connect(lambda v: self._left_max_cb and self._left_max_cb(v))
        self._right_min.valueChanged.connect(lambda v: self._right_min_cb and self._right_min_cb(v))
        self._right_max.valueChanged.connect(lambda v: self._right_max_cb and self._right_max_cb(v))
        self._left_group.finished.connect(lambda: self._left_done_cb and self._left_done_cb())
        self._right_group.finished.connect(lambda: self._right_done_cb and self._right_done_cb())

    def _create_animation(self) -> QVariantAnimation:
        anim = QVariantAnimation()
        anim.setDuration(self._duration)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    def set_callbacks(
        self,
        target: AnimationTarget,
        min_callback: Optional[Callable[[int], None]] = None,
        max_callback: Optional[Callable[[int], None]] = None,
        finished_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Set animation callbacks for target."""
        if target == AnimationTarget.LEFT_MENU:
            self._left_min_cb = min_callback
            self._left_max_cb = max_callback
            self._left_done_cb = finished_callback
        elif target == AnimationTarget.RIGHT_PANEL:
            self._right_min_cb = min_callback
            self._right_max_cb = max_callback
            self._right_done_cb = finished_callback

    def animate(self, target: AnimationTarget, frame: QFrame, target_width: int) -> None:
        """Start animation to target width."""
        current = frame.width()
        if current == target_width:
            return
        if target == AnimationTarget.LEFT_MENU:
            (group, min_anim, max_anim) = (
                self._left_group,
                self._left_min,
                self._left_max,
            )
        else:
            (group, min_anim, max_anim) = (
                self._right_group,
                self._right_min,
                self._right_max,
            )
        group.stop()
        for anim in (min_anim, max_anim):
            anim.setStartValue(current)
            anim.setEndValue(target_width)
        group.start()

    def set_immediate(self, frame: QFrame, width: int) -> None:
        """Set width immediately without animation."""
        frame.setMinimumWidth(width)
        frame.setMaximumWidth(width)

    def stop_all(self) -> None:
        """Stop all animations."""
        self._left_group.stop()
        self._right_group.stop()

    def is_animating(self, target: AnimationTarget) -> bool:
        """Check if target is animating."""
        group = self._left_group if target == AnimationTarget.LEFT_MENU else self._right_group
        return group.state() == QParallelAnimationGroup.State.Running


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
        icon_manager: IconManager,
        constants: Optional[WindowConstants] = None,
    ):
        self._main_list = main_list
        self._settings_list = settings_list
        self._icons = icon_manager
        self._constants = constants or WindowConstants()
        self._menu_items: list = []
        self._page_mapping: dict[str, str] = {}
        for widget in (main_list, settings_list):
            self._configure_list(widget)

    def _configure_list(self, widget: QListWidget) -> None:
        """Configure list widget appearance."""
        widget.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        widget.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        widget.setIconSize(self._constants.ICON_SIZE)
        widget.setUniformItemSizes(True)
        widget.setFrameShape(QFrame.Shape.NoFrame)
        widget.setSpacing(0)
        widget.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        widget.viewport().setAutoFillBackground(False)
        if MenuDelegate:
            delegate = MenuDelegate(self._constants.MENU_ITEM_HEIGHT, 5, widget)
            widget.setItemDelegate(delegate)
        widget.setProperty("collapsed", False)

    def set_menu_items(self, items: list, page_mapping: Optional[dict[str, str]] = None) -> None:
        """Set menu items."""
        self._menu_items = items
        self._page_mapping = page_mapping or {}
        self._main_list.setUpdatesEnabled(False)
        try:
            self._main_list.clear()
            for item in items:
                icon = getattr(item, "icon", "")
                title = getattr(item, "title", str(item))
                shortcut = getattr(item, "shortcut", "")
                self._add_item(self._main_list, icon, title, shortcut)
        finally:
            self._main_list.setUpdatesEnabled(True)

    def add_settings_item(self, icon_resource: str, title: str, shortcut: str = "") -> None:
        """Add settings item to settings list."""
        self._settings_list.setUpdatesEnabled(False)
        try:
            self._settings_list.clear()
            self._add_item(self._settings_list, icon_resource, title, shortcut)
        finally:
            self._settings_list.setUpdatesEnabled(True)

    def _add_item(self, widget: QListWidget, icon_res: str, title: str, shortcut: str = "") -> None:
        """Add item to list widget."""
        icon = self._icons.icon(icon_res, self._constants.ICON_SIZE)
        item = QListWidgetItem(icon, title)
        item.setToolTip(f"{title} ({shortcut})" if shortcut else title)
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
        for widget in (self._main_list, self._settings_list):
            with QSignalBlocker(widget):
                widget.setCurrentRow(-1)
                widget.clearSelection()

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
                list_item.setIcon(self._icons.icon(icon, self._constants.ICON_SIZE))
        settings_item = self._settings_list.item(0)
        if settings_item:
            settings_item.setIcon(self._icons.icon(Icons.SETTINGS, self._constants.ICON_SIZE))

    @property
    def menu_items(self) -> list:
        return self._menu_items.copy()

    @property
    def page_mapping(self) -> dict[str, str]:
        return self._page_mapping.copy()


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

    def __init__(
        self,
        container: QWidget,
        icon_manager: IconManager,
        constants: Optional[WindowConstants] = None,
    ):
        self._container = container
        self._icons = icon_manager
        self._constants = constants or WindowConstants()
        self._click_catcher = ClickCatcher(container) if ClickCatcher else FallbackClickCatcher(container)
        self._settings_panel = SettingsRootPanel(container, icon_manager) if SettingsRootPanel else FallbackPanel(container, icon_manager)
        self._theme_panel = ThemeSubPanel(container) if ThemeSubPanel else FallbackThemePanel(container)
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

    def set_rect_providers(self, settings_rect: Callable[[], QRect], left_menu_rect: Callable[[], QRect]) -> None:
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
        x = x_start if x_start + w <= container.width() - margin else max(x_start, container.width() - w - margin)
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
                btn_y = self._settings_panel.btn_theme.mapTo(self._container, QPoint(0, 0)).y()
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
            (self._settings_panel.btn_theme if hasattr(self._settings_panel, "btn_theme") else None),
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


@dataclass
class ShortcutDefinition:
    """Shortcut definition."""

    key: str
    callback: Callable[[], None]
    description: str = ""
    enabled: bool = True


class ShortcutManager:
    """Manages keyboard shortcuts."""

    __slots__ = ("_parent", "_shortcuts", "_destroyed")

    def __init__(self, parent: QWidget):
        self._parent = parent
        self._shortcuts: dict[str, tuple[QShortcut, ShortcutDefinition]] = {}
        self._destroyed = False

    def register(self, key: str, callback: Callable[[], None], description: str = "") -> None:
        """Register a keyboard shortcut."""
        if key in self._shortcuts:
            self.unregister(key)
        definition = ShortcutDefinition(key=key, callback=callback, description=description)
        shortcut = QShortcut(QKeySequence(key), self._parent)
        shortcut.activated.connect(self._safe_call(callback))
        self._shortcuts[key] = (shortcut, definition)

    def register_multiple(self, shortcuts: list[tuple[str, Callable[[], None], str]]) -> None:
        """Register multiple shortcuts."""
        for key, cb, desc in shortcuts:
            self.register(key, cb, desc)

    def register_page_shortcuts(self, go_to_page: Callable[[int], None], max_pages: int = 9) -> None:
        """Register Ctrl+1~9 page shortcuts."""
        for i in range(1, min(max_pages + 1, 10)):
            self.register(f"Ctrl+{i}", lambda idx=i - 1: go_to_page(idx), f"Go to page {i}")

    def unregister(self, key: str) -> bool:
        """Unregister a shortcut."""
        if key in self._shortcuts:
            (sc, _) = self._shortcuts.pop(key)
            sc.setEnabled(False)
            sc.deleteLater()
            return True
        return False

    def _safe_call(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Create safe callback wrapper."""

        def wrapper():
            if not self._destroyed:
                try:
                    callback()
                except Exception as e:
                    logger.error(f"Shortcut error: {e}")

        return wrapper

    def set_enabled(self, key: str, enabled: bool) -> None:
        """Set shortcut enabled state."""
        if key in self._shortcuts:
            (sc, defn) = self._shortcuts[key]
            sc.setEnabled(enabled)
            defn.enabled = enabled

    def set_all_enabled(self, enabled: bool) -> None:
        """Set all shortcuts enabled state."""
        for sc, defn in self._shortcuts.values():
            sc.setEnabled(enabled)
            defn.enabled = enabled

    def get_help_text(self) -> str:
        """Get help text with all shortcuts."""
        lines = ["Keyboard Shortcuts:", "─" * 30]
        for key, (_, defn) in sorted(self._shortcuts.items()):
            lines.append(f"{key:<20} {defn.description or key}")
        return "\n".join(lines)

    def cleanup(self) -> None:
        """Cleanup all shortcuts."""
        self._destroyed = True
        for key in list(self._shortcuts.keys()):
            self.unregister(key)


def create_standard_shortcuts(manager: ShortcutManager, handlers: dict[str, Callable[[], None]]) -> None:
    """Create standard application shortcuts."""
    shortcuts = [
        ("Escape", handlers.get("escape", lambda: None), "Close/Exit"),
        ("F11", handlers.get("fullscreen", lambda: None), "Toggle Fullscreen"),
        ("F1", handlers.get("info", lambda: None), "Show Information"),
        ("Ctrl+Tab", handlers.get("next_page", lambda: None), "Next Page"),
        ("Ctrl+Shift+Tab", handlers.get("prev_page", lambda: None), "Previous Page"),
        ("Ctrl+Shift+T", handlers.get("toggle_theme", lambda: None), "Toggle Theme"),
        ("Ctrl+L", handlers.get("toggle_left_menu", lambda: None), "Toggle Left Menu"),
        (
            "Ctrl+R",
            handlers.get("toggle_right_menu", lambda: None),
            "Toggle Right Menu",
        ),
        ("Ctrl+,", handlers.get("toggle_settings", lambda: None), "Settings"),
        ("Ctrl+E", handlers.get("toggle_edit_mode", lambda: None), "Edit Positions"),
    ]
    manager.register_multiple(shortcuts)
    if go_to := handlers.get("go_to_page"):
        manager.register_page_shortcuts(go_to)


class RightPanelManager:
    """Manages right slide panel with summary table."""

    __slots__ = (
        "_frame",
        "_container",
        "_icons",
        "_constants",
        "_is_expanded",
        "_current_page",
        "_close_cb",
        "_data_request_cb",
        "_menu_widget",
        "_hover_zone",
        "_float_button",
        "_hover_timer",
    )

    def __init__(
        self,
        frame: QFrame,
        container: QWidget,
        icon_manager: IconManager,
        constants: Optional[WindowConstants] = None,
    ):
        self._frame = frame
        self._container = container
        self._icons = icon_manager
        self._constants = constants or WindowConstants()
        self._is_expanded = False
        self._current_page = "daboard_page"
        self._close_cb: Optional[Callable[[], None]] = None
        self._data_request_cb: Optional[Callable[[list[str], int], None]] = None
        self._menu_widget = None
        self._hover_zone = None
        self._float_button = None
        self._hover_timer = QTimer()
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(self._constants.TIMER_RIGHT_HOVER)
        self._hover_timer.timeout.connect(self._on_hover_timeout)
        self._setup_ui()
        self._setup_connections()

    def _setup_ui(self) -> None:
        """Setup right panel UI."""
        layout = self._get_or_create_layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        self._frame.setFrameShape(QFrame.Shape.NoFrame)
        self._frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        if RightSlideMenuWidget:
            try:
                self._menu_widget = RightSlideMenuWidget()
                layout.addWidget(self._menu_widget)
            except Exception as e:
                logger.error(f"RightSlideMenuWidget failed: {e}")
                self._menu_widget = QLabel("Menu not available")
                layout.addWidget(self._menu_widget)
        else:
            self._menu_widget = QLabel("Menu not available")
            layout.addWidget(self._menu_widget)
        if RightEdgeHoverZone:
            try:
                self._hover_zone = RightEdgeHoverZone(self._container)
                self._hover_zone.set_hover_callback(self._on_hover_enter)
                self._hover_zone.set_leave_callback(self._on_hover_leave)
                self._hover_zone.set_click_callback(self._on_toggle_click)
            except Exception as e:
                logger.error(f"RightEdgeHoverZone failed: {e}")
        if RightMenuToggleButton:
            try:
                self._float_button = RightMenuToggleButton(self._icons, self._container, inside=False)
                self._float_button.set_expanded(False)
                self._float_button.clicked.connect(self._on_toggle_click)
                self._float_button.hide()
            except Exception as e:
                logger.error(f"RightMenuToggleButton failed: {e}")
        collapsed = self._constants.RIGHT_PANEL_WIDTH_COLLAPSED
        self._frame.setMinimumWidth(collapsed)
        self._frame.setMaximumWidth(collapsed)

    def _get_or_create_layout(self) -> QVBoxLayout:
        """Get or create frame layout."""
        existing = self._frame.layout()
        if existing:
            self._clear_layout(existing)
            if isinstance(existing, QVBoxLayout):
                return existing
            self._remove_layout(existing)
        return QVBoxLayout(self._frame)

    def _clear_layout(self, layout: QLayout) -> None:
        """Clear all widgets from layout."""
        while layout.count():
            item = layout.takeAt(0)
            if w := item.widget():
                w.setParent(None)
                w.deleteLater()
            if child := item.layout():
                self._clear_layout(child)

    def _remove_layout(self, layout: QLayout) -> None:
        """Remove layout from frame."""
        self._clear_layout(layout)
        temp = QWidget()
        temp.setLayout(layout)
        temp.deleteLater()

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        if self._menu_widget and hasattr(self._menu_widget, "closed"):
            self._menu_widget.closed.connect(lambda: self._close_cb and self._close_cb())
        if self._menu_widget and hasattr(self._menu_widget, "data_request"):
            self._menu_widget.data_request.connect(lambda d, days: self._data_request_cb and self._data_request_cb(d, days))

    def _on_toggle_click(self) -> None:
        """Handle toggle button click."""
        if self._close_cb:
            self._close_cb()

    def _on_hover_enter(self) -> None:
        """Handle hover enter."""
        if not self._is_expanded and self._float_button:
            self._hover_timer.stop()
            self._float_button.show()
            self._float_button.raise_()

    def _on_hover_leave(self) -> None:
        """Handle hover leave."""
        if not self._is_expanded:
            self._hover_timer.start()

    def _on_hover_timeout(self) -> None:
        """Handle hover timeout."""
        if not self._is_expanded and self._float_button:
            if not self._float_button.underMouse():
                self._float_button.hide()

    @property
    def frame(self) -> QFrame:
        return self._frame

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def menu_widget(self):
        return self._menu_widget

    def set_close_callback(self, callback: Callable[[], None]) -> None:
        """Set close callback."""
        self._close_cb = callback

    def set_data_request_callback(self, callback: Callable[[list[str], int], None]) -> None:
        """Set data request callback."""
        self._data_request_cb = callback

    def set_expanded(self, expanded: bool, *, animate: bool = True) -> tuple[int, int]:
        """Set expanded state and return (current, target) widths."""
        self._is_expanded = expanded
        if self._float_button:
            self._float_button.hide()
        if self._hover_zone:
            if expanded:
                self._hover_zone.hide()
            else:
                self._hover_zone.show()
        exp_w = self._constants.RIGHT_PANEL_WIDTH_EXPANDED
        col_w = self._constants.RIGHT_PANEL_WIDTH_COLLAPSED
        target = exp_w if expanded else col_w
        current = self._frame.width()
        if not animate:
            self._frame.setMinimumWidth(target)
            self._frame.setMaximumWidth(target)
        return (current, target)

    def set_page(self, page_name: str) -> None:
        """Set current page."""
        self._current_page = page_name
        if self._menu_widget and hasattr(self._menu_widget, "set_page"):
            self._menu_widget.set_page(page_name)

    def update_positions(self, title_height: int, stack_rect: QRect) -> None:
        """Update hover zone and button positions."""
        h = self._container.height() - title_height
        hover_w = self._constants.RIGHT_HOVER_ZONE_WIDTH
        if self._hover_zone:
            self._hover_zone.setGeometry(stack_rect.right() - hover_w, title_height, hover_w, h)
        if self._float_button:
            y = title_height + (h - self._float_button.height()) // 2
            self._float_button.move(stack_rect.right() - self._float_button.width(), y)

    def update_icons(self) -> None:
        """Update icons with current theme."""
        if self._float_button and hasattr(self._float_button, "update_icons"):
            self._float_button.update_icons()

    def cleanup(self) -> None:
        """Cleanup resources."""
        self._hover_timer.stop()


__all__ = [
    "AnimationManager",
    "AnimationTarget",
    "MenuManager",
    "PanelManager",
    "ShortcutManager",
    "ShortcutDefinition",
    "create_standard_shortcuts",
    "RightPanelManager",
]
