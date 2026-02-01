"""
Header View - MVVM Architecture.

Binds to ShellViewModel for theme and sidebar state.
Passive view that delegates all interactions to ViewModel.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional, Tuple

from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

if TYPE_CHECKING:
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


class HeaderView:
    """
    Header view component.

    Passive view that:
    - Binds to ShellViewModel signals
    - Delegates user actions to ViewModel
    - Renders based on state
    - Displays logo and application title
    """

    def __init__(
        self,
        container: QFrame,
        toggle_btn: Optional[QPushButton],
        title_label: Optional[QLabel],
        title_icon: Optional[QLabel],
        window_buttons: Tuple[Optional[QPushButton], ...],
        shell_vm: "ShellViewModel",
    ):
        self._container = container
        self._toggle_btn = toggle_btn
        self._title_label = title_label
        self._title_icon = title_icon
        self._shell_vm = shell_vm

        # Unpack window buttons safely
        self._minimize_btn = window_buttons[0] if len(window_buttons) > 0 else None
        self._restore_btn = window_buttons[1] if len(window_buttons) > 1 else None
        self._close_btn = window_buttons[2] if len(window_buttons) > 2 else None

        # Initialize with current ViewModel state
        self._current_theme = shell_vm.theme
        self._current_expanded = shell_vm.sidebar_expanded

        # Setup logo and title first
        self._setup_logo_and_title()

        self._setup_connections()
        self._bind_viewmodel()

        # Apply initial state
        self._update_visibility()
        self._update_toggle_icon()

    def _setup_logo_and_title(self) -> None:
        """Setup logo icon and application title."""
        # Setup logo
        if self._title_icon:
            self._load_logo()

        # Setup title text
        if self._title_label:
            self._title_label.setText("iFactory")
            self._title_label.setStyleSheet(
                """
                QLabel {
                    font-size: 14px;
                    font-weight: bold;
                    padding-left: 4px;
                }
            """
            )

    def _load_logo(self) -> None:
        """Load and set the logo image."""
        if not self._title_icon:
            return

        logo_loaded = False

        # Try loading from Qt resources first
        try:
            pixmap = QPixmap(":/icon/logo.png")
            if not pixmap.isNull():
                scaled = pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self._title_icon.setPixmap(scaled)
                self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                logo_loaded = True
                logger.debug("[HeaderView] Logo loaded from resources")
        except Exception as e:
            logger.debug(f"[HeaderView] Could not load logo from resources: {e}")

        # Try alternative paths if resource loading failed
        if not logo_loaded:
            alternative_paths = [
                "src/iFactory/presentation/resources/icon/logo.png",
                "iFactory/presentation/resources/icon/logo.png",
                "resources/icon/logo.png",
                "icon/logo.png",
            ]

            for path in alternative_paths:
                if os.path.exists(path):
                    try:
                        pixmap = QPixmap(path)
                        if not pixmap.isNull():
                            scaled = pixmap.scaled(28, 28, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            self._title_icon.setPixmap(scaled)
                            self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
                            logo_loaded = True
                            logger.debug(f"[HeaderView] Logo loaded from path: {path}")
                            break
                    except Exception as e:
                        logger.debug(f"[HeaderView] Could not load logo from {path}: {e}")

        # Fallback to emoji/text if no image found
        if not logo_loaded:
            self._title_icon.setText("🏭")
            self._title_icon.setStyleSheet(
                """
                QLabel {
                    font-size: 20px;
                    padding: 4px;
                }
            """
            )
            self._title_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            logger.warning("[HeaderView] Using fallback emoji for logo")

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
        if theme != self._current_theme:
            self._current_theme = theme
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
        """Handle minimize button click."""
        window = self._container.window()
        if window:
            window.showMinimized()

    def _on_restore(self) -> None:
        """Handle restore/maximize button click."""
        window = self._container.window()
        if window:
            if window.isMaximized():
                window.showNormal()
            else:
                window.showMaximized()

    def _on_close(self) -> None:
        """Handle close button click."""
        window = self._container.window()
        if window:
            window.close()

    def _update_visibility(self) -> None:
        """Update title label and icon visibility based on sidebar state."""
        if self._title_label:
            self._title_label.setVisible(self._current_expanded)
            logger.debug(f"[HeaderView] Title label visible: {self._current_expanded}")

        if self._title_icon:
            self._title_icon.setVisible(self._current_expanded)
            logger.debug(f"[HeaderView] Title icon visible: {self._current_expanded}")

    def _update_title_style(self) -> None:
        """Update title label style based on theme."""
        if not self._title_label:
            return

        is_dark = self._current_theme == "dark"
        text_color = "#F1F5F9" if is_dark else "#1E293B"

        self._title_label.setStyleSheet(
            f"""
            QLabel {{
                font-size: 14px;
                font-weight: bold;
                padding-left: 4px;
                color: {text_color};
            }}
        """
        )

    def _update_toggle_icon(self) -> None:
        """Update toggle button icon based on state."""
        if not self._toggle_btn:
            return

        is_dark = self._current_theme == "dark"
        suffix = "-white" if is_dark else ""

        if self._current_expanded:
            icon_name = f"arrow_menu_close{suffix}.svg"
        else:
            icon_name = f"arrow_menu_open{suffix}.svg"

        # Try to set icon from resources
        icon = QIcon(f":/icon/{icon_name}")
        if not icon.isNull():
            self._toggle_btn.setIcon(icon)
            self._toggle_btn.setIconSize(QSize(20, 20))
            self._toggle_btn.setText("")  # Clear any text
            self._toggle_btn.setStyleSheet(
                """
                QPushButton {
                    border: none;
                    background: transparent;
                    padding: 4px;
                }
                QPushButton:hover {
                    background: rgba(128, 128, 128, 0.1);
                    border-radius: 4px;
                }
            """
            )
        else:
            # Fallback to text-based indicator
            arrow_text = "◀" if self._current_expanded else "▶"
            self._toggle_btn.setText(arrow_text)
            self._toggle_btn.setIcon(QIcon())  # Clear icon
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
        """
        Render header based on state.

        Legacy compatibility method - state comes from Redux store.
        Primary updates now come via ViewModel signals.
        """
        sidebar_expanded = state.get("sidebar_expanded", False)
        theme = state.get("theme", "light")

        # Update internal state if changed
        if theme != self._current_theme:
            self._current_theme = theme
            self._update_toggle_icon()
            self._update_title_style()

        if sidebar_expanded != self._current_expanded:
            self._current_expanded = sidebar_expanded
            self._update_visibility()
            self._update_toggle_icon()


__all__ = ["HeaderView"]
