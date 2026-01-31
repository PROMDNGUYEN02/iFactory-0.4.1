"""
Status Bar Component - System Health Indicators.
Refactored for Dark Mode compatibility and Dynamic Styling.
"""

from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout, QFrame
from PySide6.QtCore import Qt
from ...ui_state.selectors import select_system_status, select_last_log_message
from ...resources.themes.theme_manager import theme_manager


class StatusBarView:
    """
    Manages the application status bar, showing DB connections and system messages.
    """

    def __init__(self, status_bar: QStatusBar):
        self._bar = status_bar
        self._current_theme_mode = "light"
        self._setup_ui()

    def _setup_ui(self):
        # Initial style, will be updated in render
        self._apply_theme_style("light")

        # Message Label
        self._lbl_msg = QLabel("Ready")
        self._lbl_msg.setStyleSheet("padding-left: 10px; font-size: 12px;")
        self._bar.addWidget(self._lbl_msg, 1)

        # Right container
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

    def _create_indicator(self, text):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        # Default style, updated dynamically
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

    def _apply_theme_style(self, mode: str):
        is_dark = mode == "dark"
        bg_color = "#2d2d2d" if is_dark else "#FAFAFA"
        border_color = "#444444" if is_dark else "#E5E5E5"
        text_color = "#E0E0E0" if is_dark else "#333333"
        sep_color = "#555555" if is_dark else "#CCCCCC"

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

        if hasattr(self, "_sep"):
            self._sep.setStyleSheet(f"color: {sep_color};")

    def render(self, state: dict):
        """Update system indicators and Theme."""
        # 1. Theme Check
        new_theme = state.get("theme", "light")
        if new_theme != self._current_theme_mode:
            self._current_theme_mode = new_theme
            self._apply_theme_style(new_theme)

        # 2. Data Update
        status = select_system_status(state)
        msg = select_last_log_message(state)

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

    def _update_indicator(self, label, is_active, text_ok, text_err):
        is_dark = self._current_theme_mode == "dark"

        if is_active:
            # Green
            bg = "#064E3B" if is_dark else "#D1FAE5"
            text = "#34D399" if is_dark else "#065F46"
            border = "#059669" if is_dark else "#10B981"

            label.setText(f"● {text_ok}")
            label.setStyleSheet(
                f"""
                background-color: {bg}; color: {text}; 
                border: 1px solid {border}; border-radius: 12px; 
                padding: 2px 10px; font-weight: bold;
                """
            )
        else:
            # Red
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
