"""
Status Bar Component - System Health Indicators.
"""

from PySide6.QtWidgets import QStatusBar, QLabel, QWidget, QHBoxLayout, QFrame
from PySide6.QtCore import Qt
from ...ui_state.selectors import select_system_status, select_last_log_message


class StatusBarView:
    """
    Manages the application status bar, showing DB connections and system messages.
    """

    def __init__(self, status_bar: QStatusBar):
        self._bar = status_bar
        self._setup_ui()

    def _setup_ui(self):
        self._bar.setStyleSheet(
            """
            QStatusBar {
                background-color: #FAFAFA;
                border-top: 1px solid #E5E5E5;
                color: #333;
            }
        """
        )

        # Message Label
        self._lbl_msg = QLabel("Ready")
        self._lbl_msg.setStyleSheet("color: #666666; padding-left: 10px; font-size: 12px;")
        self._bar.addWidget(self._lbl_msg, 1)

        # Right container
        self._container = QWidget()
        layout = QHBoxLayout(self._container)
        layout.setContentsMargins(0, 0, 15, 0)
        layout.setSpacing(15)

        self._lbl_sqlite = self._create_indicator("Local DB")
        self._lbl_mssql = self._create_indicator("Remote DB")
        self._lbl_mode = QLabel("ONLINE")
        self._lbl_mode.setStyleSheet("font-weight: bold; font-size: 11px; color: #10B981;")

        layout.addWidget(self._lbl_sqlite)
        layout.addWidget(self._lbl_mssql)

        sep = QFrame()
        sep.setFrameShape(QFrame.VLine)
        sep.setStyleSheet("color: #CCCCCC;")
        layout.addWidget(sep)

        layout.addWidget(self._lbl_mode)

        self._bar.addPermanentWidget(self._container)

    def _create_indicator(self, text):
        lbl = QLabel(text)
        lbl.setAlignment(Qt.AlignCenter)
        lbl.setStyleSheet(
            """
            QLabel {
                background-color: transparent;
                color: #999999;
                font-weight: 600;
                font-size: 11px;
                padding: 4px 8px;
                border: 1px solid #E0E0E0;
                border-radius: 10px;
            }
        """
        )
        return lbl

    def render(self, state: dict):
        """Update system indicators."""
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
        if is_active:
            label.setText(f"● {text_ok}")
            label.setStyleSheet(
                """
                background-color: #D1FAE5; color: #065F46; 
                border: 1px solid #10B981; border-radius: 12px; 
                padding: 2px 10px; font-weight: bold;
            """
            )
        else:
            label.setText(f"○ {text_err}")
            label.setStyleSheet(
                """
                background-color: #FEE2E2; color: #991B1B; 
                border: 1px solid #EF4444; border-radius: 12px; 
                padding: 2px 10px; font-weight: bold;
            """
            )
