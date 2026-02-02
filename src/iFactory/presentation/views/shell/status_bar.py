# File: presentation/views/shell/status_bar.py
"""
Status Bar View - MVVM Architecture.

Displays system status and connection indicators.
Uses ThemeService for styling.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStatusBar, QWidget

from ...state.selectors import select_system_status

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


class StatusBarView:
    """Status bar showing system status using ThemeService."""

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
        self._lbl_msg.setText(status.message)
        self._update_indicator(self._lbl_mssql, status.mssql_connected, "Remote: On", "Remote: Off")
        self._update_indicator(self._lbl_sqlite, status.sqlite_connected, "Local: On", "Local: Err")

        tokens = self._theme_service.tokens

        if status.is_online:
            self._lbl_mode.setText("ONLINE SYSTEM")
            self._lbl_mode.setStyleSheet(f"color: {tokens.success}; font-weight: 900;")
        elif status.sqlite_connected:
            self._lbl_mode.setText("OFFLINE MODE")
            self._lbl_mode.setStyleSheet(f"color: {tokens.warning}; font-weight: 900;")
        else:
            self._lbl_mode.setText("SYSTEM HALTED")
            self._lbl_mode.setStyleSheet(f"color: {tokens.error}; font-weight: 900;")

    def _setup(self) -> None:
        """Setup status bar UI."""
        self._lbl_msg = QLabel("Ready")
        self._lbl_msg.setStyleSheet("padding-left: 10px; font-size: 12px;")
        self._bar.addWidget(self._lbl_msg, 1)

        self._container = QWidget()
        layout = QHBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 15, 0)
        layout.setSpacing(15)

        self._lbl_sqlite = self._create_indicator("Local DB")
        self._lbl_mssql = self._create_indicator("Remote DB")
        self._lbl_mode = QLabel("ONLINE")
        self._lbl_mode.setStyleSheet("font-weight: bold; font-size: 11px;")

        layout.addWidget(self._lbl_sqlite)
        layout.addWidget(self._lbl_mssql)

        self._sep = QFrame()
        self._sep.setFrameShape(QFrame.VLine)
        layout.addWidget(self._sep)

        layout.addWidget(self._lbl_mode)

        self._bar.addPermanentWidget(self._container)

    def _create_indicator(self, text: str) -> QLabel:
        """Create a status indicator label."""
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            """
            QLabel {
                background-color: transparent;
                font-weight: 600;
                font-size: 11px;
                padding: 4px 8px;
                border-radius: 10px;
            }
        """
        )
        return lbl

    def _apply_theme_style(self) -> None:
        """Apply theme styles using ThemeService."""
        tokens = self._theme_service.tokens

        self._bar.setStyleSheet(
            f"""
            QStatusBar {{
                background-color: {tokens.slide_bg};
                border-top: 1px solid {tokens.border};
                color: {tokens.app_fg};
            }}
        """
        )

        self._lbl_msg.setStyleSheet(f"color: {tokens.app_fg}; padding-left: 10px; font-size: 12px;")
        self._sep.setStyleSheet(f"background-color: {tokens.border};")

    def _update_indicator(self, label: QLabel, is_active: bool, text_ok: str, text_err: str) -> None:
        """Update status indicator style."""
        tokens = self._theme_service.tokens

        if is_active:
            bg = tokens.get_rgba("success", 0.15)
            text = tokens.success
            border = tokens.success
            label.setText(f"● {text_ok}")
        else:
            bg = tokens.get_rgba("error", 0.15)
            text = tokens.error
            border = tokens.error
            label.setText(f"○ {text_err}")

        label.setStyleSheet(
            f"""
            background-color: {bg}; 
            color: {text};
            border: 1px solid {border}; 
            border-radius: 12px;
            padding: 2px 10px; 
            font-weight: bold;
        """
        )

    def render(self, state: Dict[str, Any]) -> None:
        """Render status bar based on state (legacy compatibility)."""
        status = select_system_status(state)
        msg = status.get("message", "Ready")
        self._lbl_msg.setText(msg)

        mssql = status.get("mssql", False)
        sqlite = status.get("sqlite", False)

        self._update_indicator(self._lbl_mssql, mssql, "Remote: On", "Remote: Off")
        self._update_indicator(self._lbl_sqlite, sqlite, "Local: On", "Local: Err")

        tokens = self._theme_service.tokens

        if mssql and sqlite:
            self._lbl_mode.setText("ONLINE SYSTEM")
            self._lbl_mode.setStyleSheet(f"color: {tokens.success}; font-weight: 900;")
        elif not mssql and sqlite:
            self._lbl_mode.setText("OFFLINE MODE")
            self._lbl_mode.setStyleSheet(f"color: {tokens.warning}; font-weight: 900;")
        else:
            self._lbl_mode.setText("SYSTEM HALTED")
            self._lbl_mode.setStyleSheet(f"color: {tokens.error}; font-weight: 900;")


__all__ = ["StatusBarView"]
