# File: src/iFactory/presentation/managers/right_panel_manager.py
"""
Right Panel Manager - Manages right slide panel with summary table.
"""
from __future__ import annotations
from typing import Any, Callable, Optional, Dict

from PySide6.QtCore import QTimer, QRect
from PySide6.QtWidgets import QFrame, QWidget, QVBoxLayout


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
        self, frame: QFrame, container: QWidget, icon_manager: Any, constants: Any
    ):
        self._frame = frame
        self._container = container
        self._icons = icon_manager
        self._constants = constants

        self._is_expanded = False
        self._current_page = "daboard_page"
        self._close_cb: Optional[Callable[[], None]] = None
        self._data_request_cb: Optional[Callable[[Dict[str, int], int], None]] = None

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

        # Try importing optional widgets with fallback
        try:
            from iFactory.ui.widgets.right_slide_menu import RightSlideMenuWidget
            from iFactory.ui.widgets.right_panel_components import (
                RightEdgeHoverZone,
                RightMenuToggleButton,
            )

            self._menu_widget = RightSlideMenuWidget()
            layout.addWidget(self._menu_widget)
        except Exception:
            self._menu_widget = None

        try:
            from iFactory.ui.widgets.right_panel_components import (
                RightEdgeHoverZone,
                RightMenuToggleButton,
            )

            self._hover_zone = RightEdgeHoverZone(self._container)
            self._hover_zone.set_hover_callback(self._on_hover_enter)
            self._hover_zone.set_leave_callback(self._on_hover_leave)
            self._hover_zone.set_click_callback(self._on_toggle_click)
        except Exception:
            pass

        try:
            from iFactory.ui.widgets.right_panel_components import RightMenuToggleButton

            self._float_button = RightMenuToggleButton(
                self._icons, self._container, inside=False
            )
            self._float_button.set_expanded(False)
            self._float_button.clicked.connect(self._on_toggle_click)
            self._float_button.hide()
        except Exception:
            pass

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

    def _clear_layout(self, layout) -> None:
        """Clear all widgets from layout."""
        while layout.count():
            item = layout.takeAt(0)
            if w := item.widget():
                w.setParent(None)
                w.deleteLater()
            if child := item.layout():
                self._clear_layout(child)

    def _remove_layout(self, layout) -> None:
        """Remove layout from frame."""
        self._clear_layout(layout)
        temp = QWidget()
        temp.setLayout(layout)
        temp.deleteLater()

    def _setup_connections(self) -> None:
        """Setup signal connections."""
        if self._menu_widget and hasattr(self._menu_widget, "closed"):
            self._menu_widget.closed.connect(
                lambda: self._close_cb and self._close_cb()
            )
        if self._menu_widget and hasattr(self._menu_widget, "data_request"):
            self._menu_widget.data_request.connect(
                lambda d, days: self._data_request_cb and self._data_request_cb(d, days)
            )

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

    def set_data_request_callback(
        self, callback: Callable[[Dict[str, int], int], None]
    ) -> None:
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
            self._hover_zone.setGeometry(
                stack_rect.right() - hover_w, title_height, hover_w, h
            )

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
