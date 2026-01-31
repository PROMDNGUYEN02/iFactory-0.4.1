"""
Header Component - Top bar navigation and window controls.
Refactored for Robustness against Missing Widgets.
"""

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QAction, QPixmap
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QSizePolicy

from ...resources.themes.theme_manager import theme_manager


class HeaderView:
    def __init__(
        self,
        container_frame: QFrame,
        toggle_btn: QPushButton,
        title_label: QLabel,
        title_icon: QLabel,
        min_btn: QPushButton,
        restore_btn: QPushButton,
        close_btn: QPushButton,
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

        self._current_theme_mode = "light"

        self._setup_layout_fixes()
        self._setup_icons()
        self._connect_signals()

    def _setup_layout_fixes(self):
        if not self._frame:
            return

        if not self._frame.layout():
            layout = QHBoxLayout(self._frame)
            self._frame.setLayout(layout)

        layout = self._frame.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.setAlignment(Qt.AlignVCenter)

        if self._toggle_btn:
            self._toggle_btn.setObjectName("menu_toggle_btn")

        if self._title_icon:
            self._title_icon.setScaledContents(True)
            self._title_icon.setFixedSize(32, 32)

    def _setup_icons(self):
        self._update_theme_icons()

    def _update_theme_icons(self):
        if self._toggle_btn:
            self._toggle_btn.setIcon(QIcon(theme_manager.get_icon_path(":/icon/arrow_menu_close.svg")))

        # [FIX] Safety checks for None widgets
        if self._min_btn:
            self._min_btn.setIcon(QIcon(":/icon/minus.svg"))  # Ensure this icon exists in resource or use fallback
        if self._restore_btn:
            self._restore_btn.setIcon(QIcon(":/icon/square.svg"))
        if self._close_btn:
            self._close_btn.setIcon(QIcon(":/icon/close.svg"))

        if self._title_icon:
            logo_path = ":/icon/logo.png"
            self._title_icon.setPixmap(QPixmap(logo_path))

    def _connect_signals(self):
        if self._toggle_btn:
            self._toggle_btn.clicked.connect(self._controller.handle_left_menu_toggle)

        if self._frame:
            window = self._frame.window()

            if self._min_btn:
                self._min_btn.clicked.connect(window.showMinimized)

            if self._restore_btn:

                def restore_maximize():
                    if window.isMaximized():
                        window.showNormal()
                    else:
                        window.showMaximized()

                self._restore_btn.clicked.connect(restore_maximize)

            if self._close_btn:
                self._close_btn.clicked.connect(window.close)

    def render(self, state: dict):
        new_theme = state.get("theme", "light")
        if new_theme != self._current_theme_mode:
            self._current_theme_mode = new_theme
            self._update_theme_icons()

        is_expanded = state.get("left_menu_expanded", True)
        if self._toggle_btn:
            icon_key = ":/icon/arrow_menu_close.svg" if is_expanded else ":/icon/arrow_menu_open.svg"
            self._toggle_btn.setIcon(QIcon(theme_manager.get_icon_path(icon_key)))
