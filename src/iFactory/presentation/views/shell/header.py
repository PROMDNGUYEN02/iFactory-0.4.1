# File: presentation/views/shell/header.py
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton

from ...constants.layout import Layout
from ...resources.themes import get_theme_manager
from ...state.selectors import select_sidebar_expanded, select_theme

if TYPE_CHECKING:
    from ...controllers.shell_controller import ShellController


class HeaderView:
    def __init__(
        self,
        container: QFrame,
        toggle_btn: Optional[QPushButton],
        title_label: Optional[QLabel],
        title_icon: Optional[QLabel],
        window_buttons: Tuple[Optional[QPushButton], ...],
        controller: "ShellController",
    ):
        self._container = container
        self._toggle_btn = toggle_btn
        self._title_label = title_label
        self._title_icon = title_icon
        self._window_buttons = window_buttons
        self._controller = controller
        self._theme_manager = get_theme_manager()

        self._current_theme = "light"
        self._setup()

    def _setup(self) -> None:
        if not self._container:
            return

        layout = self._container.layout()
        if not layout:
            layout = QHBoxLayout(self._container)
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignVCenter)

        if self._toggle_btn:
            self._toggle_btn.setText("")
            self._toggle_btn.setFixedSize(40, 40)
            self._toggle_btn.setCursor(Qt.PointingHandCursor)
            self._toggle_btn.clicked.connect(self._controller.toggle_sidebar_menu)

        for btn in self._window_buttons:
            if btn:
                btn.setText("")
                btn.setFixedSize(36, 36)
                btn.setCursor(Qt.PointingHandCursor)

        if self._title_icon:
            self._title_icon.setText("")
            self._title_icon.setScaledContents(True)
            self._title_icon.setFixedSize(28, 28)

        if self._title_label:
            self._title_label.setText("iFactory Monitor")

        if len(self._window_buttons) >= 3:
            min_btn, restore_btn, close_btn = self._window_buttons[0], self._window_buttons[1], self._window_buttons[2]
            window = self._container.window()

            if min_btn and window:
                min_btn.clicked.connect(window.showMinimized)
            if close_btn and window:
                close_btn.clicked.connect(window.close)
            if restore_btn and window:
                restore_btn.clicked.connect(lambda: window.showNormal() if window.isMaximized() else window.showMaximized())

    def render(self, state: dict) -> None:
        theme = select_theme(state)
        is_expanded = select_sidebar_expanded(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._update_icons(is_expanded)

        width = Layout.SIDEBAR_EXPANDED_WIDTH if is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if self._toggle_btn:
            icon_name = "arrow_menu_close" if is_expanded else "arrow_menu_open"
            icon_path = self._theme_manager.get_icon_path(f":/icon/{icon_name}.svg")
            self._toggle_btn.setIcon(QIcon(icon_path))

        if self._title_icon:
            self._title_icon.setVisible(is_expanded)
        if self._title_label:
            self._title_label.setVisible(is_expanded)

        layout = self._container.layout()
        if layout:
            if is_expanded:
                layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                layout.setContentsMargins(10, 0, 0, 0)
            else:
                layout.setAlignment(Qt.AlignCenter)
                layout.setContentsMargins(0, 0, 0, 0)

    def _update_icons(self, is_expanded: bool) -> None:
        if self._toggle_btn:
            icon_name = "arrow_menu_close" if is_expanded else "arrow_menu_open"
            icon_path = self._theme_manager.get_icon_path(f":/icon/{icon_name}.svg")
            self._toggle_btn.setIcon(QIcon(icon_path))


__all__ = ["HeaderView"]
