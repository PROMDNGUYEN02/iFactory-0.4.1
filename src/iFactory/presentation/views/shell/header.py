# File: presentation/views/shell/header.py
from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Tuple

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QFont, QPixmap
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
        self._ui_toggle_btn = toggle_btn
        self._ui_title_label = title_label
        self._ui_title_icon = title_icon
        self._window_buttons = window_buttons
        self._controller = controller
        self._theme_manager = get_theme_manager()
        self._current_theme = "light"
        self._is_expanded = False

        self._setup_header()

    def _setup_header(self) -> None:
        if not self._container:
            return

        if self._ui_title_icon:
            self._ui_title_icon.setText("")
            self._ui_title_icon.setFixedSize(32, 32)
            self._ui_title_icon.setScaledContents(True)
            self._ui_title_icon.setPixmap(QPixmap(":/icon/logo.png"))
            self._ui_title_icon.setStyleSheet("background: transparent; padding: 4px;")

        if self._ui_title_label:
            self._ui_title_label.setText("iFactory")
            self._ui_title_label.setFont(QFont("Segoe UI", 12, QFont.DemiBold))
            self._ui_title_label.setStyleSheet("background: transparent; padding-left: 4px;")

        if self._ui_toggle_btn:
            self._ui_toggle_btn.setText("")
            self._ui_toggle_btn.setFixedSize(40, 32)
            self._ui_toggle_btn.setCursor(Qt.PointingHandCursor)
            self._ui_toggle_btn.setToolTip("Toggle Menu (Ctrl+M)")
            self._ui_toggle_btn.setIconSize(QSize(20, 20))
            self._ui_toggle_btn.clicked.connect(self._controller.toggle_sidebar_menu)

        layout = self._container.layout()
        if layout:
            layout.setContentsMargins(8, 4, 8, 4)
            layout.setSpacing(4)

        self._apply_styles()

    def _apply_styles(self) -> None:
        is_dark = self._current_theme == "dark"

        if is_dark:
            bg = "rgba(30, 41, 59, 0.98)"
            border = "rgba(51, 65, 85, 0.8)"
            text_color = "#F1F5F9"
            btn_hover = "rgba(71, 85, 105, 0.6)"
        else:
            bg = "rgba(255, 255, 255, 0.98)"
            border = "rgba(226, 232, 240, 0.8)"
            text_color = "#1E293B"
            btn_hover = "rgba(241, 245, 249, 0.8)"

        self._container.setStyleSheet(
            f"""
            QFrame#title_frame {{
                background-color: {bg};
                border: none;
                border-bottom: 1px solid {border};
            }}
        """
        )

        if self._ui_title_label:
            self._ui_title_label.setStyleSheet(
                f"""
                QLabel {{
                    color: {text_color};
                    background: transparent;
                    font-size: 13px;
                    font-weight: 600;
                    padding-left: 6px;
                }}
            """
            )

        if self._ui_toggle_btn:
            self._ui_toggle_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: transparent;
                    border: none;
                    border-radius: 6px;
                    padding: 6px;
                }}
                QPushButton:hover {{
                    background-color: {btn_hover};
                }}
                QPushButton:pressed {{
                    background-color: rgba(128, 128, 128, 0.3);
                }}
            """
            )

    def _update_toggle_icon(self) -> None:
        if not self._ui_toggle_btn:
            return
        icon_name = "arrow_menu_close" if self._is_expanded else "arrow_menu_open"
        icon_path = self._theme_manager.get_icon_path(f":/icon/{icon_name}.svg")
        self._ui_toggle_btn.setIcon(QIcon(icon_path))

    def _reorder_layout(self) -> None:
        layout = self._container.layout()
        if not layout:
            return

        if self._is_expanded:
            layout.setDirection(QHBoxLayout.LeftToRight)
        else:
            layout.setDirection(QHBoxLayout.RightToLeft)

    def render(self, state: dict) -> None:
        theme = select_theme(state)
        is_expanded = select_sidebar_expanded(state)

        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_styles()

        if is_expanded != self._is_expanded:
            self._is_expanded = is_expanded
            self._reorder_layout()

        self._update_toggle_icon()

        width = Layout.SIDEBAR_EXPANDED_WIDTH if is_expanded else Layout.SIDEBAR_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if self._ui_title_icon:
            self._ui_title_icon.setVisible(is_expanded)
        if self._ui_title_label:
            self._ui_title_label.setVisible(is_expanded)

        layout = self._container.layout()
        if layout:
            if is_expanded:
                layout.setContentsMargins(10, 4, 6, 4)
            else:
                layout.setContentsMargins(5, 4, 5, 4)


__all__ = ["HeaderView"]
