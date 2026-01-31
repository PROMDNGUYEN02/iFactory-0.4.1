"""
Header Component - Application Title Bar & Window Controls.
Handles optional UI elements gracefully.
"""

from typing import Optional
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QWidget, QLabel, QPushButton, QFrame

from ...constants.ui_constants import UIConstants
from ...resources.themes.theme_manager import theme_manager
from ...ui_state.selectors import select_left_menu_expanded


class HeaderView:
    """
    Manages the top header bar.
    Robustly handles missing UI widgets by treating them as optional.
    """

    def __init__(
        self,
        container_frame: QFrame,
        toggle_btn: Optional[QPushButton],
        title_label: Optional[QLabel],
        title_icon: Optional[QLabel],
        min_btn: Optional[QPushButton],
        restore_btn: Optional[QPushButton],
        close_btn: Optional[QPushButton],
        controller,
    ):

        self._frame = container_frame
        self._toggle_btn = toggle_btn
        self._title_label = title_label
        self._title_icon = title_icon

        self._min_btn = min_btn
        self._restore_btn = restore_btn
        self._close_btn = close_btn

        self._controller = controller

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        # Logo
        if self._title_icon:
            self._title_icon.setPixmap(QPixmap(":/icon/logo.png").scaled(24, 24, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self._title_icon.setText("")
            self._title_icon.setContentsMargins(10, 0, 0, 0)

        # Title
        if self._title_label:
            self._title_label.setText("iFactory")
            self._title_label.setStyleSheet("font-size: 14px; font-weight: bold;")

        # Toggle Button
        if self._toggle_btn:
            self._toggle_btn.setText("")
            self._toggle_btn.setIconSize(QSize(20, 20))
            self._toggle_btn.setCursor(Qt.PointingHandCursor)
            self._toggle_btn.setToolTip("Toggle Menu (Ctrl+M)")

    def _connect_signals(self):
        if self._toggle_btn:
            self._toggle_btn.clicked.connect(self._controller.handle_left_menu_toggle)

        # Window Controls
        # Note: We assume the frame is attached to the Main Window
        window = self._frame.window()

        if self._min_btn:
            self._min_btn.clicked.connect(window.showMinimized)

        if self._restore_btn:
            self._restore_btn.clicked.connect(lambda: window.showNormal() if window.isMaximized() else window.showMaximized())

        if self._close_btn:
            self._close_btn.clicked.connect(window.close)

    def render(self, state: dict):
        """Update header based on state."""
        is_expanded = select_left_menu_expanded(state)

        # Update Width to match Sidebar
        width = UIConstants.MENU_EXPANDED_WIDTH if is_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        self._frame.setFixedWidth(width)

        # Visibility
        if self._title_label:
            self._title_label.setVisible(is_expanded)
        if self._title_icon:
            self._title_icon.setVisible(is_expanded)

        # Toggle Icon
        if self._toggle_btn:
            btn_key = ":/icon/close.svg" if is_expanded else ":/icon/open.svg"
            self._toggle_btn.setIcon(QIcon(theme_manager.get_icon_path(btn_key)))

            # Update Toggle Button Style Object Name
            self._toggle_btn.setObjectName("menu_close_btn" if is_expanded else "menu_open_btn")
            # Force restyle
            self._toggle_btn.style().unpolish(self._toggle_btn)
            self._toggle_btn.style().polish(self._toggle_btn)
