# File: presentation/views/shell/header.py
"""
Header View - MVVM Architecture.

Binds to ShellViewModel for theme and sidebar state.
Uses ThemeService for styling and icons.
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

    Passive view that:
    - Binds to ShellViewModel signals
    - Uses ThemeService for styling and icons
    - Delegates user actions to ViewModel
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

        self._setup_logo_and_title()
        self._setup_connections()
        self._bind_viewmodel()
        self._update_visibility()
        self._update_toggle_icon()

    def _setup_logo_and_title(self) -> None:
        """Setup logo icon and application title using IconProvider."""
        if self._title_icon:
            self._load_logo()

        if self._title_label:
            self._title_label.setText("iFactory")
            self._update_title_style()

    def _load_logo(self) -> None:
        """Load and set the logo image using ThemeService."""
        if not self._title_icon:
            return

        # Use ThemeService to get cached pixmap
        pixmap = self._theme_service.get_pixmap(Icons.LOGO, QSize(28, 28))

        if not pixmap.isNull():
            self._title_icon.setPixmap(pixmap)
            self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        else:
            # Fallback to emoji
            self._title_icon.setText("🏭")
            self._title_icon.setStyleSheet("QLabel { font-size: 20px; padding: 4px; }")
            self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logger.warning("[HeaderView] Failed to load logo, using fallback")

    def _setup_connections(self) -> None:
        """Connect UI events to ViewModel methods."""
        if self._toggle_btn:
            self._toggle_btn.clicked.connect(self._shell_vm.toggle_sidebar)

        if self._minimize_btn:
            self._minimize_btn.clicked.connect(self._on_minimize)

        if self._restore_btn:
            self._restore_btn.clicked.connect(self._on_restore)

        if self._close_btn:
            self._close_btn.clicked.connect(self._on_close)

    def _bind_viewmodel(self) -> None:
        """Bind to ViewModel signals."""
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.sidebarChanged.connect(self._on_sidebar_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change from ViewModel."""
        self._update_toggle_icon()
        self._update_title_style()

    @Slot(bool)
    def _on_sidebar_changed(self, expanded: bool) -> None:
        """Handle sidebar change from ViewModel."""
        if expanded != self._current_expanded:
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
        """Update title label and icon visibility."""
        if self._title_label:
            self._title_label.setVisible(self._current_expanded)

        if self._title_icon:
            self._title_icon.setVisible(self._current_expanded)

    def _update_title_style(self) -> None:
        """Update title label style using ThemeService tokens."""
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
        """Update toggle button icon using enum-based icons."""
        if not self._toggle_btn:
            return

        # Use Icons enum - ThemeService handles theme-appropriate path
        icon_enum = Icons.LEFT_PANEL_CLOSE if self._current_expanded else Icons.LEFT_PANEL_OPEN

        # Get cached icon from ThemeService
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
                    background: {tokens.get_rgba("hover", 0.5)};
                    border-radius: 4px;
                }}
            """
            )
        else:
            # Fallback to text arrow
            arrow_text = "◀" if self._current_expanded else "▶"
            self._toggle_btn.setText(arrow_text)
            self._toggle_btn.setIcon(icon)  # Clear any existing icon
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
