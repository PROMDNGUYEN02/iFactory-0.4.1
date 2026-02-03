# File: presentation/views/shell/header.py
"""
Header View - MVVM Architecture.

OPTIMIZED:
1. Skip redundant theme updates
2. Cached icon loading
3. Batch style updates
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

from ...resources.icons import Icons

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


class HeaderView:
    """
    Header view component.

    OPTIMIZED:
    - Skip redundant theme/sidebar updates
    - Cached styles
    """

    def __init__(
        self,
        container: QFrame,
        toggle_btn: Optional[QPushButton],
        title_label: Optional[QLabel],
        title_icon: Optional[QLabel],
        window_buttons: Tuple[Optional[QPushButton], ...],
        shell_vm: "ShellViewModel",
        theme_service: "ThemeService",
    ):
        self._container = container
        self._toggle_btn = toggle_btn
        self._title_label = title_label
        self._title_icon = title_icon
        self._shell_vm = shell_vm
        self._theme_service = theme_service

        self._minimize_btn = window_buttons[0] if len(window_buttons) > 0 else None
        self._restore_btn = window_buttons[1] if len(window_buttons) > 1 else None
        self._close_btn = window_buttons[2] if len(window_buttons) > 2 else None

        self._current_expanded = shell_vm.sidebar_expanded
        self._current_theme = theme_service.current_theme

        self._setup_logo_and_title()
        self._setup_connections()
        self._bind_viewmodel()
        self._update_visibility()
        self._update_toggle_icon()

    def _setup_logo_and_title(self) -> None:
        if self._title_icon:
            self._load_logo()

        if self._title_label:
            self._title_label.setText("iFactory")
            self._update_title_style()

    def _load_logo(self) -> None:
        if not self._title_icon:
            return

        pixmap = self._theme_service.get_pixmap(Icons.LOGO, QSize(28, 28))

        if not pixmap.isNull():
            self._title_icon.setPixmap(pixmap)
            self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            self._title_icon.setText("🏭")
            self._title_icon.setStyleSheet("QLabel { font-size: 20px; padding: 4px; }")
            self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logger.warning("[HeaderView] Failed to load logo, using fallback")

    def _setup_connections(self) -> None:
        if self._toggle_btn:
            self._toggle_btn.clicked.connect(self._shell_vm.toggle_sidebar)

        if self._minimize_btn:
            self._minimize_btn.clicked.connect(self._on_minimize)

        if self._restore_btn:
            self._restore_btn.clicked.connect(self._on_restore)

        if self._close_btn:
            self._close_btn.clicked.connect(self._on_close)

    def _bind_viewmodel(self) -> None:
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.sidebarChanged.connect(self._on_sidebar_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change - OPTIMIZED."""
        if theme == self._current_theme:
            return

        self._current_theme = theme
        self._update_toggle_icon()
        self._update_title_style()

    @Slot(bool)
    def _on_sidebar_changed(self, expanded: bool) -> None:
        """Handle sidebar change - OPTIMIZED."""
        if expanded == self._current_expanded:
            return

        self._current_expanded = expanded
        self._update_visibility()
        self._update_toggle_icon()

    def _on_minimize(self) -> None:
        window = self._container.window()
        if window:
            window.showMinimized()

    def _on_restore(self) -> None:
        window = self._container.window()
        if window:
            if window.isMaximized():
                window.showNormal()
            else:
                window.showMaximized()

    def _on_close(self) -> None:
        window = self._container.window()
        if window:
            window.close()

    def _update_visibility(self) -> None:
        if self._title_label:
            self._title_label.setVisible(self._current_expanded)

        if self._title_icon:
            self._title_icon.setVisible(self._current_expanded)

    def _update_title_style(self) -> None:
        if not self._title_label:
            return

        tokens = self._theme_service.tokens

        self._title_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                padding-left: 4px;
                color: {tokens.app_fg};
            }}
        """
        )

    def _update_toggle_icon(self) -> None:
        if not self._toggle_btn:
            return

        icon_enum = Icons.LEFT_PANEL_CLOSE if self._current_expanded else Icons.LEFT_PANEL_OPEN
        icon = self._theme_service.get_icon(icon_enum)
        tokens = self._theme_service.tokens

        if not icon.isNull():
            self._toggle_btn.setIcon(icon)
            self._toggle_btn.setIconSize(QSize(20, 20))
            self._toggle_btn.setText("")
            self._toggle_btn.setStyleSheet(
                f"""
                QPushButton {{
                    border: none;
                    background: transparent;
                    padding: 4px;
                }}
                QPushButton:hover {{
                    background: {tokens.interactive_hover};
                    border-radius: 4px;
                }}
            """
            )
        else:
            arrow_text = "◀" if self._current_expanded else "▶"
            self._toggle_btn.setText(arrow_text)
            self._toggle_btn.setIcon(icon)
            self._toggle_btn.setStyleSheet(
                """
                QPushButton {
                    border: none;
                    background: transparent;
                    padding: 4px;
                    font-size: 12px;
                }
                QPushButton:hover {
                    background: rgba(128, 128, 128, 0.1);
                    border-radius: 4px;
                }
            """
            )

    def render(self, state: Dict[str, Any]) -> None:
        """Render header based on state (legacy compatibility)."""
        sidebar_expanded = state.get("sidebar_expanded", False)

        if sidebar_expanded != self._current_expanded:
            self._current_expanded = sidebar_expanded
            self._update_visibility()
            self._update_toggle_icon()


__all__ = ["HeaderView"]
