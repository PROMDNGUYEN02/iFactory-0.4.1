# File: presentation/views/shell/header.py
"""
Header View - MVVM Architecture.

OPTIMIZED:
1. Skip redundant theme updates
2. Cached icon loading
3. Batch style updates
4. Proper lifecycle management
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional, Tuple, Dict, Any
from dataclasses import dataclass

from PySide6.QtCore import Qt, Slot, QSize
from PySide6.QtWidgets import QFrame, QLabel, QPushButton

from ...resources.icons import Icons

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


# =============================================================================
# State Model
# =============================================================================


@dataclass
class HeaderState:
    """Header state for comparison."""

    sidebar_expanded: bool
    theme: str


# =============================================================================
# Header View
# =============================================================================


class HeaderView:
    """
    Header view component with optimized rendering.

    Features:
    - Logo and title display
    - Sidebar toggle button
    - Window control buttons (minimize, restore, close)
    - Theme-aware styling with caching

    NOTE: No __slots__ - needed for Qt signal weak references
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
        # Store references
        self._container = container
        self._toggle_btn = toggle_btn
        self._title_label = title_label
        self._title_icon = title_icon
        self._shell_vm = shell_vm
        self._theme_service = theme_service

        # Window buttons
        self._minimize_btn = window_buttons[0] if len(window_buttons) > 0 else None
        self._restore_btn = window_buttons[1] if len(window_buttons) > 1 else None
        self._close_btn = window_buttons[2] if len(window_buttons) > 2 else None

        # State tracking
        self._current_state = HeaderState(
            sidebar_expanded=shell_vm.sidebar_expanded,
            theme=theme_service.current_theme,
        )

        # Style cache
        self._style_cache: Dict[str, str] = {}

        # Initialize
        self._setup_logo_and_title()
        self._setup_connections()
        self._bind_viewmodel()
        self._apply_current_state()

    # =========================================================================
    # Setup
    # =========================================================================

    def _setup_logo_and_title(self) -> None:
        """Setup logo and title elements."""
        if self._title_icon:
            self._load_logo()

        if self._title_label:
            self._title_label.setText("iFactory")
            self._update_title_style()

    def _load_logo(self) -> None:
        """Load and display logo."""
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
        """Setup button click connections."""
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

    # =========================================================================
    # Signal Handlers
    # =========================================================================

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change with state comparison."""
        if theme == self._current_state.theme:
            return

        self._current_state = HeaderState(
            sidebar_expanded=self._current_state.sidebar_expanded,
            theme=theme,
        )
        self._style_cache.clear()  # Invalidate style cache
        self._update_toggle_icon()
        self._update_title_style()

    @Slot(bool)
    def _on_sidebar_changed(self, expanded: bool) -> None:
        """Handle sidebar change with state comparison."""
        if expanded == self._current_state.sidebar_expanded:
            return

        self._current_state = HeaderState(
            sidebar_expanded=expanded,
            theme=self._current_state.theme,
        )
        self._update_visibility()
        self._update_toggle_icon()

    # =========================================================================
    # Window Actions
    # =========================================================================

    def _on_minimize(self) -> None:
        """Minimize window."""
        window = self._container.window()
        if window:
            window.showMinimized()

    def _on_restore(self) -> None:
        """Toggle maximize/restore."""
        window = self._container.window()
        if window:
            if window.isMaximized():
                window.showNormal()
            else:
                window.showMaximized()

    def _on_close(self) -> None:
        """Close window."""
        window = self._container.window()
        if window:
            window.close()

    # =========================================================================
    # UI Updates
    # =========================================================================

    def _apply_current_state(self) -> None:
        """Apply current state to UI."""
        self._update_visibility()
        self._update_toggle_icon()

    def _update_visibility(self) -> None:
        """Update element visibility based on sidebar state."""
        expanded = self._current_state.sidebar_expanded

        if self._title_label:
            self._title_label.setVisible(expanded)

        if self._title_icon:
            self._title_icon.setVisible(expanded)

    def _update_title_style(self) -> None:
        """Update title label style."""
        if not self._title_label:
            return

        cache_key = f"title_{self._current_state.theme}"
        if cache_key not in self._style_cache:
            tokens = self._theme_service.tokens
            self._style_cache[
                cache_key
            ] = f"""
                QLabel {{
                    font-size: 14px;
                    font-weight: bold;
                    padding-left: 4px;
                    color: {tokens.app_fg};
                }}
            """

        self._title_label.setStyleSheet(self._style_cache[cache_key])

    def _update_toggle_icon(self) -> None:
        """Update toggle button icon and style."""
        if not self._toggle_btn:
            return

        expanded = self._current_state.sidebar_expanded
        icon_enum = Icons.LEFT_PANEL_CLOSE if expanded else Icons.LEFT_PANEL_OPEN
        icon = self._theme_service.get_icon(icon_enum)
        tokens = self._theme_service.tokens

        if not icon.isNull():
            self._toggle_btn.setIcon(icon)
            self._toggle_btn.setIconSize(QSize(20, 20))
            self._toggle_btn.setText("")

            cache_key = f"toggle_icon_{self._current_state.theme}"
            if cache_key not in self._style_cache:
                self._style_cache[
                    cache_key
                ] = f"""
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
            self._toggle_btn.setStyleSheet(self._style_cache[cache_key])
        else:
            # Fallback to text
            arrow_text = "◀" if expanded else "▶"
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

    # =========================================================================
    # Legacy Compatibility
    # =========================================================================

    def render(self, state: Dict[str, Any]) -> None:
        """Render header based on state (legacy compatibility)."""
        sidebar_expanded = state.get("sidebar_expanded", False)

        if sidebar_expanded != self._current_state.sidebar_expanded:
            self._current_state = HeaderState(
                sidebar_expanded=sidebar_expanded,
                theme=self._current_state.theme,
            )
            self._update_visibility()
            self._update_toggle_icon()

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
        except (RuntimeError, TypeError):
            pass


__all__ = ["HeaderView"]
