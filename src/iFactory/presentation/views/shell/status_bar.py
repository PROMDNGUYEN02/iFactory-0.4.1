"""
Status Bar View - MVVM Architecture.

Displays system status and connection indicators.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any, Dict

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QStatusBar, QWidget

from ...resources.themes import get_theme_manager
from ...state.selectors import select_system_status, select_theme

if TYPE_CHECKING:
    from ...viewmodels import ShellViewModel

logger = logging.getLogger(__name__)


class StatusBarView:
    """
    Status bar showing system status.

    Displays:
    - Connection status (MSSQL, SQLite)
    - Current mode (Online/Offline)
    - Status messages
    """

    def __init__(
        self,
        status_bar: QStatusBar,
        shell_vm: "ShellViewModel" = None,
    ):
        self._bar = status_bar
        self._shell_vm = shell_vm
        self._theme_manager = get_theme_manager()
        self._current_theme = "light"
        self._setup()

        if self._shell_vm:
            self._bind_viewmodel()

    def _bind_viewmodel(self) -> None:
        """Bind to ViewModel signals."""
        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.systemStatusChanged.connect(self._on_status_changed)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_theme_style(theme)

    @Slot(object)
    def _on_status_changed(self, status) -> None:
        """Handle system status change from ViewModel."""
        self._lbl_msg.setText(status.message)
        self._update_indicator(self._lbl_mssql, status.mssql_connected, "Remote: On", "Remote: Off")
        self._update_indicator(self._lbl_sqlite, status.sqlite_connected, "Local: On", "Local: Err")

        if status.is_online:
            self._lbl_mode.setText("ONLINE SYSTEM")
            self._lbl_mode.setStyleSheet("color: #10B981; font-weight: 900;")
        elif status.sqlite_connected:
            self._lbl_mode.setText("OFFLINE MODE")
            self._lbl_mode.setStyleSheet("color: #F59E0B; font-weight: 900;")
        else:
            self._lbl_mode.setText("SYSTEM HALTED")
            self._lbl_mode.setStyleSheet("color: #EF4444; font-weight: 900;")

    def _setup(self) -> None:
        self._apply_theme_style("light")

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

    def _apply_theme_style(self, mode: str) -> None:
        is_dark = mode == "dark"
        bg_color = "#2d2d2d" if is_dark else "#FAFAFA"
        border_color = "#444444" if is_dark else "#E5E5E5"
        text_color = "#E0E0E0" if is_dark else "#333333"

        self._bar.setStyleSheet(
            f"""
            QStatusBar {{
                background-color: {bg_color};
                border-top: 1px solid {border_color};
                color: {text_color};
            }}
        """
        )

        if hasattr(self, "_lbl_msg"):
            self._lbl_msg.setStyleSheet(f"color: {text_color}; padding-left: 10px; font-size: 12px;")

    def _update_indicator(self, label: QLabel, is_active: bool, text_ok: str, text_err: str) -> None:
        is_dark = self._current_theme == "dark"

        if is_active:
            bg = "#064E3B" if is_dark else "#D1FAE5"
            text = "#34D399" if is_dark else "#065F46"
            border = "#059669" if is_dark else "#10B981"
            label.setText(f"● {text_ok}")
        else:
            bg = "#7F1D1D" if is_dark else "#FEE2E2"
            text = "#F87171" if is_dark else "#991B1B"
            border = "#B91C1C" if is_dark else "#EF4444"
            label.setText(f"○ {text_err}")

        label.setStyleSheet(
            f"""
            background-color: {bg}; color: {text};
            border: 1px solid {border}; border-radius: 12px;
            padding: 2px 10px; font-weight: bold;
        """
        )

    def render(self, state: Dict[str, Any]) -> None:
        """
        Render status bar based on state.

        Legacy compatibility - updates come via ViewModel signals if available.
        """
        theme = select_theme(state)
        if theme != self._current_theme:
            self._current_theme = theme
            self._apply_theme_style(theme)

        status = select_system_status(state)
        msg = status.get("message", "Ready")
        self._lbl_msg.setText(msg)

        mssql = status.get("mssql", False)
        sqlite = status.get("sqlite", False)

        self._update_indicator(self._lbl_mssql, mssql, "Remote: On", "Remote: Off")
        self._update_indicator(self._lbl_sqlite, sqlite, "Local: On", "Local: Err")

        if mssql and sqlite:
            self._lbl_mode.setText("ONLINE SYSTEM")
            self._lbl_mode.setStyleSheet("color: #10B981; font-weight: 900;")
        elif not mssql and sqlite:
            self._lbl_mode.setText("OFFLINE MODE")
            self._lbl_mode.setStyleSheet("color: #F59E0B; font-weight: 900;")
        else:
            self._lbl_mode.setText("SYSTEM HALTED")
            self._lbl_mode.setStyleSheet("color: #EF4444; font-weight: 900;")


__all__ = ["StatusBarView"]
