# File: presentation/views/shell/status_bar.py
"""
Status Bar View - MVVM Architecture.

Displays system status and connection indicators.
Uses ThemeService and component library for styling.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict, Optional

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStatusBar, QWidget

from ...state.selectors import select_system_status

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


class ConnectionIndicator(QLabel):
    """
    Connection status indicator with colored background.

    States:
    - Connected: green background with checkmark
    - Disconnected: red background with X
    """

    def __init__(self, name: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._name = name
        self._theme_service = theme_service
        self._is_connected = False

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_style()

    def set_connected(self, connected: bool, ok_text: str = "On", err_text: str = "Off") -> None:
        """Update connection state."""
        self._is_connected = connected

        if connected:
            self.setText(f"● {self._name}: {ok_text}")
        else:
            self.setText(f"○ {self._name}: {err_text}")

        self._apply_style()

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        if self._is_connected:
            bg_color = tokens.success_subtle
            text_color = tokens.success
            border_color = tokens.success
        else:
            bg_color = tokens.error_subtle
            text_color = tokens.error
            border_color = tokens.error

        self.setStyleSheet(
            f"""
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
        )


class SystemModeLabel(QLabel):
    """
    System mode indicator.

    Modes:
    - ONLINE SYSTEM: All connections good (green)
    - OFFLINE MODE: Local only (yellow)
    - SYSTEM HALTED: All connections failed (red)
    """

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__("INITIALIZING", parent)
        self._theme_service = theme_service
        self._mode = "initializing"

        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_style()

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_style()

    def set_mode(self, mode: str) -> None:
        """
        Set system mode.

        Args:
            mode: "online", "offline", or "halted"
        """
        self._mode = mode.lower()

        mode_texts = {
            "online": "ONLINE SYSTEM",
            "offline": "OFFLINE MODE",
            "halted": "SYSTEM HALTED",
            "initializing": "INITIALIZING",
        }

        self.setText(mode_texts.get(self._mode, "UNKNOWN"))
        self._apply_style()

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        mode_colors = {
            "online": tokens.success,
            "offline": tokens.warning,
            "halted": tokens.error,
            "initializing": tokens.text_muted,
        }

        color = mode_colors.get(self._mode, tokens.text_muted)

        self.setStyleSheet(
            f"""
            QLabel {{
                color: {color};
                font-weight: {tokens.font_weight_bold};
                font-size: {tokens.font_size_sm};
            }}
        """
        )


class StatusBarView:
    """
    Status bar showing system status.

    Uses custom indicator components for consistent theming.
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
        self._apply_theme_style()

    @Slot(object)
    def _on_status_changed(self, status) -> None:
        """Handle system status change from ViewModel."""
        # Update message
        self._lbl_msg.setText(status.message)

        # Update connection indicators
        self._indicator_mssql.set_connected(status.mssql_connected, "Remote: On", "Remote: Off")
        self._indicator_sqlite.set_connected(status.sqlite_connected, "Local: On", "Local: Err")

        # Update system mode
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
        """Apply theme styles using ThemeService."""
        tokens = self._theme_service.tokens

        self._bar.setStyleSheet(
            f"""
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
        )

        self._lbl_msg.setStyleSheet(
            f"""
            color: {tokens.text_secondary};
            padding-left: {tokens.space_3};
            font-size: {tokens.font_size_sm};
        """
        )

        self._sep.setStyleSheet(f"background-color: {tokens.border_default};")

    def render(self, state: Dict[str, Any]) -> None:
        """Render status bar based on state (legacy compatibility)."""
        status = select_system_status(state)
        msg = status.get("message", "Ready")
        self._lbl_msg.setText(msg)

        mssql = status.get("mssql", False)
        sqlite = status.get("sqlite", False)

        self._indicator_mssql.set_connected(mssql, "Remote: On", "Remote: Off")
        self._indicator_sqlite.set_connected(sqlite, "Local: On", "Local: Err")

        if mssql and sqlite:
            self._mode_label.set_mode("online")
        elif not mssql and sqlite:
            self._mode_label.set_mode("offline")
        else:
            self._mode_label.set_mode("halted")


__all__ = ["StatusBarView"]
