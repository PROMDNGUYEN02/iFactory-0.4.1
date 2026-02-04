# File: presentation/views/shell/status_bar.py
"""
Status Bar View - MVVM Architecture.

Displays system status and connection indicators.
Uses ThemeService and component library for styling.

OPTIMIZATIONS:
- State comparison for skip redundant updates
- Cached styles per theme
- Proper lifecycle management
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Dict, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStatusBar, QWidget

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel
    from ...viewmodels.models.shell_model import SystemStatusModel

logger = logging.getLogger(__name__)


# =============================================================================
# State Models
# =============================================================================


@dataclass(frozen=True, slots=True)
class StatusBarState:
    """Immutable status bar state."""

    mssql_connected: bool
    sqlite_connected: bool
    message: str
    theme: str


# =============================================================================
# Connection Indicator
# =============================================================================


class ConnectionIndicator(QLabel):
    """
    Connection status indicator with colored background.

    States:
    - Connected: green background with checkmark
    - Disconnected: red background with X

    OPTIMIZATIONS:
    - Skip redundant style updates
    - Theme change handling
    """

    # NOTE: No __slots__ here - needed for Qt signal connections

    def __init__(
        self,
        name: str,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._name = name
        self._theme_service = theme_service
        self._is_connected = False
        self._current_theme = theme_service.current_theme
        self._style_cache: Dict[str, str] = {}

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme == self._current_theme:
            return
        self._current_theme = theme
        self._style_cache.clear()
        self._apply_style()

    def set_connected(
        self,
        connected: bool,
        ok_text: str = "On",
        err_text: str = "Off",
    ) -> None:
        """Update connection state."""
        expected_text = f"● {self._name}: {ok_text}" if connected else f"○ {self._name}: {err_text}"

        # Skip if no change
        if connected == self._is_connected and self.text() == expected_text:
            return

        self._is_connected = connected
        self.setText(expected_text)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply current style with caching."""
        cache_key = f"{self._current_theme}_{self._is_connected}"

        if cache_key not in self._style_cache:
            tokens = self._theme_service.tokens

            if self._is_connected:
                bg_color = tokens.success_subtle
                text_color = tokens.success
                border_color = tokens.success
            else:
                bg_color = tokens.error_subtle
                text_color = tokens.error
                border_color = tokens.error

            self._style_cache[
                cache_key
            ] = f"""
                QLabel {{
                    background-color: {bg_color};
                    color: {text_color};
                    border: 1px solid {border_color};
                    border-radius: {tokens.radius_full};
                    padding: {tokens.space_1} {tokens.space_3};
                    font-weight: {tokens.font_weight_semibold};
                    font-size: {tokens.font_size_sm};
                }}
            """

        self.setStyleSheet(self._style_cache[cache_key])

    def dispose(self) -> None:
        """Clean up resources."""
        self._style_cache.clear()
        try:
            self._theme_service.themeChanged.disconnect(self._on_theme_changed)
        except (RuntimeError, TypeError):
            pass


# =============================================================================
# System Mode Label
# =============================================================================


class SystemModeLabel(QLabel):
    """
    System mode indicator.

    Modes:
    - ONLINE SYSTEM: All connections good (green)
    - OFFLINE MODE: Local only (yellow)
    - SYSTEM HALTED: All connections failed (red)

    OPTIMIZATIONS:
    - Skip redundant updates
    - Cached styles
    """

    # NOTE: No __slots__ here - needed for Qt signal connections

    MODE_TEXTS: Dict[str, str] = {
        "online": "ONLINE SYSTEM",
        "offline": "OFFLINE MODE",
        "halted": "SYSTEM HALTED",
        "initializing": "INITIALIZING",
    }

    def __init__(
        self,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__("INITIALIZING", parent)
        self._theme_service = theme_service
        self._mode = "initializing"
        self._current_theme = theme_service.current_theme
        self._style_cache: Dict[str, str] = {}

        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme == self._current_theme:
            return
        self._current_theme = theme
        self._style_cache.clear()
        self._apply_style()

    def set_mode(self, mode: str) -> None:
        """Set system mode."""
        mode_lower = mode.lower()
        if mode_lower == self._mode:
            return

        self._mode = mode_lower
        self.setText(self.MODE_TEXTS.get(self._mode, "UNKNOWN"))
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply current style with caching."""
        cache_key = f"{self._current_theme}_{self._mode}"

        if cache_key not in self._style_cache:
            tokens = self._theme_service.tokens

            mode_colors = {
                "online": tokens.success,
                "offline": tokens.warning,
                "halted": tokens.error,
                "initializing": tokens.text_muted,
            }

            color = mode_colors.get(self._mode, tokens.text_muted)

            self._style_cache[
                cache_key
            ] = f"""
                QLabel {{
                    color: {color};
                    font-weight: {tokens.font_weight_bold};
                    font-size: {tokens.font_size_sm};
                }}
            """

        self.setStyleSheet(self._style_cache[cache_key])

    def dispose(self) -> None:
        """Clean up resources."""
        self._style_cache.clear()
        try:
            self._theme_service.themeChanged.disconnect(self._on_theme_changed)
        except (RuntimeError, TypeError):
            pass


# =============================================================================
# Status Bar View
# =============================================================================


class StatusBarView:
    """
    Status bar showing system status.

    Features:
    - Message display
    - Connection indicators (Local/Remote)
    - System mode indicator

    OPTIMIZATIONS:
    - State comparison for skip redundant updates
    - Cached styles per theme
    - Proper lifecycle management

    NOTE: No __slots__ - needed for Qt signal weak references
    """

    def __init__(
        self,
        status_bar: QStatusBar,
        shell_vm: "ShellViewModel",
        theme_service: "ThemeService",
    ):
        self._bar = status_bar
        self._shell_vm = shell_vm
        self._theme_service = theme_service

        # State tracking
        self._state = StatusBarState(
            mssql_connected=False,
            sqlite_connected=False,
            message="Ready",
            theme=theme_service.current_theme,
        )

        # Style cache
        self._style_cache: Dict[str, str] = {}

        # UI components (initialized in _setup)
        self._lbl_msg: Optional[QLabel] = None
        self._container: Optional[QWidget] = None
        self._indicator_sqlite: Optional[ConnectionIndicator] = None
        self._indicator_mssql: Optional[ConnectionIndicator] = None
        self._sep: Optional[QFrame] = None
        self._mode_label: Optional[SystemModeLabel] = None

        self._setup()
        self._apply_theme_style()
        self._bind_viewmodel()

    def _bind_viewmodel(self) -> None:
        """Bind to ViewModel signals."""
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.systemStatusChanged.connect(self._on_status_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme == self._state.theme:
            return

        self._state = StatusBarState(
            mssql_connected=self._state.mssql_connected,
            sqlite_connected=self._state.sqlite_connected,
            message=self._state.message,
            theme=theme,
        )
        self._style_cache.clear()
        self._apply_theme_style()

    @Slot(object)
    def _on_status_changed(self, status: "SystemStatusModel") -> None:
        """Handle system status change from ViewModel."""
        new_state = StatusBarState(
            mssql_connected=status.mssql_connected,
            sqlite_connected=status.sqlite_connected,
            message=status.message,
            theme=self._state.theme,
        )

        # Skip if no change
        if new_state == self._state:
            return

        self._state = new_state

        # Update UI components
        if self._lbl_msg:
            self._lbl_msg.setText(status.message)
        if self._indicator_mssql:
            self._indicator_mssql.set_connected(status.mssql_connected, "Remote: On", "Remote: Off")
        if self._indicator_sqlite:
            self._indicator_sqlite.set_connected(status.sqlite_connected, "Local: On", "Local: Err")

        # Update mode based on connection status
        if self._mode_label:
            if status.is_online:
                self._mode_label.set_mode("online")
            elif status.sqlite_connected:
                self._mode_label.set_mode("offline")
            else:
                self._mode_label.set_mode("halted")

    def _setup(self) -> None:
        """Setup status bar UI."""
        # Message label (left side)
        self._lbl_msg = QLabel("Ready")
        self._bar.addWidget(self._lbl_msg, 1)

        # Right side container
        self._container = QWidget()
        layout = QHBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 15, 0)
        layout.setSpacing(12)

        # Connection indicators
        self._indicator_sqlite = ConnectionIndicator("Local", self._theme_service)
        self._indicator_mssql = ConnectionIndicator("Remote", self._theme_service)

        layout.addWidget(self._indicator_sqlite)
        layout.addWidget(self._indicator_mssql)

        # Separator
        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.Shape.VLine)
        self._sep.setFixedHeight(16)
        layout.addWidget(self._sep)

        # System mode
        self._mode_label = SystemModeLabel(self._theme_service)
        layout.addWidget(self._mode_label)

        self._bar.addPermanentWidget(self._container)

    def _apply_theme_style(self) -> None:
        """Apply theme styles with caching."""
        tokens = self._theme_service.tokens
        theme = self._state.theme

        # Status bar style
        bar_key = f"bar_{theme}"
        if bar_key not in self._style_cache:
            self._style_cache[
                bar_key
            ] = f"""
                QStatusBar {{
                    background-color: {tokens.surface_panel};
                    border-top: 1px solid {tokens.border_default};
                    color: {tokens.text_primary};
                    min-height: {tokens.layout_statusbar_height};
                }}
                QStatusBar::item {{
                    border: none;
                }}
            """
        self._bar.setStyleSheet(self._style_cache[bar_key])

        # Message label style
        if self._lbl_msg:
            msg_key = f"msg_{theme}"
            if msg_key not in self._style_cache:
                self._style_cache[
                    msg_key
                ] = f"""
                    color: {tokens.text_secondary};
                    padding-left: {tokens.space_3};
                    font-size: {tokens.font_size_sm};
                """
            self._lbl_msg.setStyleSheet(self._style_cache[msg_key])

        # Separator style
        if self._sep:
            sep_key = f"sep_{theme}"
            if sep_key not in self._style_cache:
                self._style_cache[sep_key] = f"background-color: {tokens.border_default};"
            self._sep.setStyleSheet(self._style_cache[sep_key])

    # =========================================================================
    # Legacy Compatibility
    # =========================================================================

    def render(self, state: Dict[str, any]) -> None:
        """Render status bar based on state (legacy compatibility)."""
        from ...state.selectors import select_system_status

        status = select_system_status(state)
        msg = status.get("message", "Ready")
        if self._lbl_msg:
            self._lbl_msg.setText(msg)

        mssql = status.get("mssql", False)
        sqlite = status.get("sqlite", False)

        if self._indicator_mssql:
            self._indicator_mssql.set_connected(mssql, "Remote: On", "Remote: Off")
        if self._indicator_sqlite:
            self._indicator_sqlite.set_connected(sqlite, "Local: On", "Local: Err")

        if self._mode_label:
            if mssql and sqlite:
                self._mode_label.set_mode("online")
            elif not mssql and sqlite:
                self._mode_label.set_mode("offline")
            else:
                self._mode_label.set_mode("halted")

    # =========================================================================
    # Lifecycle
    # =========================================================================

    def dispose(self) -> None:
        """Clean up resources."""
        self._style_cache.clear()

        # Dispose child components
        if self._indicator_sqlite:
            self._indicator_sqlite.dispose()
        if self._indicator_mssql:
            self._indicator_mssql.dispose()
        if self._mode_label:
            self._mode_label.dispose()

        # Disconnect signals
        try:
            self._shell_vm.themeChanged.disconnect(self._on_theme_changed)
            self._shell_vm.systemStatusChanged.disconnect(self._on_status_changed)
        except (RuntimeError, TypeError):
            pass


__all__ = ["StatusBarView", "ConnectionIndicator", "SystemModeLabel"]
