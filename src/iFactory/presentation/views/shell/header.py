"""
Header Component.
Refactored for Clean Aesthetics.
"""

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QHBoxLayout, QPushButton

from ...resources.themes.theme_manager import theme_manager
from ...constants.ui_constants import UIConstants


class HeaderView:
    def __init__(self, container_frame, toggle_btn, title_label, title_icon, min_btn, restore_btn, close_btn, controller):
        self._frame = container_frame
        self._toggle_btn = toggle_btn
        self._title_label = title_label
        self._title_icon = title_icon
        self._btns = [min_btn, restore_btn, close_btn]
        self._controller = controller
        self._current_theme_mode = "light"

        if self._frame:
            self._apply_clean_layout()
            self._remove_ui_artifacts()
            self._connect_signals()

    def _apply_clean_layout(self):
        """Enforce strict alignment."""
        if not self._frame.layout():
            layout = QHBoxLayout(self._frame)
            self._frame.setLayout(layout)

        layout = self._frame.layout()
        layout.setContentsMargins(5, 0, 5, 0)
        layout.setSpacing(5)
        layout.setAlignment(Qt.AlignVCenter)

    def _remove_ui_artifacts(self):
        """Wipe all default text from Qt Designer."""
        if self._toggle_btn:
            self._toggle_btn.setText("")  # Kill 'PushButton' text
            self._toggle_btn.setFixedSize(40, 40)  # Perfect square
            self._toggle_btn.setCursor(Qt.PointingHandCursor)

        for btn in self._btns:
            if btn:
                btn.setText("")
                btn.setFixedSize(36, 36)
                btn.setCursor(Qt.PointingHandCursor)

        if self._title_icon:
            self._title_icon.setText("")
            self._title_icon.setScaledContents(True)
            self._title_icon.setFixedSize(28, 28)

        if self._title_label:
            self._title_label.setText("iFactory Monitor")

    def _connect_signals(self):
        if self._toggle_btn:
            self._toggle_btn.clicked.connect(self._controller.handle_left_menu_toggle)

        if self._frame:
            window = self._frame.window()
            min_b, res_b, cls_b = self._btns
            if min_b:
                min_b.clicked.connect(window.showMinimized)
            if cls_b:
                cls_b.clicked.connect(window.close)
            if res_b:
                res_b.clicked.connect(lambda: window.showNormal() if window.isMaximized() else window.showMaximized())

    def render(self, state: dict):
        new_theme = state.get("theme", "light")
        if new_theme != self._current_theme_mode:
            self._current_theme_mode = new_theme
            self._update_icons(state.get("left_menu_expanded", True))

        is_expanded = state.get("left_menu_expanded", True)

        # Header Size Logic
        target_width = UIConstants.MENU_EXPANDED_WIDTH if is_expanded else UIConstants.MENU_COLLAPSED_WIDTH
        self._frame.setFixedWidth(target_width)

        # Toggle Icon Logic
        if self._toggle_btn:
            icon = ":/icon/arrow_menu_close.svg" if is_expanded else ":/icon/arrow_menu_open.svg"
            self._toggle_btn.setIcon(QIcon(theme_manager.get_icon_path(icon)))

        # Visibility Logic
        if self._title_icon:
            self._title_icon.setVisible(is_expanded)
        if self._title_label:
            self._title_label.setVisible(is_expanded)

        # Alignment Logic: Center Toggle when collapsed
        layout = self._frame.layout()
        if is_expanded:
            layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            layout.setContentsMargins(10, 0, 0, 0)
        else:
            layout.setAlignment(Qt.AlignCenter)
            layout.setContentsMargins(0, 0, 0, 0)

    def _update_icons(self, is_expanded):
        if self._toggle_btn:
            icon = ":/icon/arrow_menu_close.svg" if is_expanded else ":/icon/arrow_menu_open.svg"
            self._toggle_btn.setIcon(QIcon(theme_manager.get_icon_path(icon)))

        # Update window control icons...
        pass
