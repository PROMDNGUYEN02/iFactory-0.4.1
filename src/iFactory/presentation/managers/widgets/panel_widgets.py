"""Panel widgets for settings and overlays."""

from __future__ import annotations
import logging
from typing import Optional, Callable
from PySide6.QtCore import Qt, QSize, Signal, QPoint
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPixmap

logger = logging.getLogger(__name__)
__all__ = ["ClickCatcher", "SettingsRootPanel", "ThemeSubPanel"]
ICON_EXPAND = ":/icon/expand.svg"


class ClickCatcher(QWidget):
    """Transparent overlay for catching clicks."""

    clicked = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setStyleSheet("background: transparent;")
        self._in_press = False
        self.hide()

    def mousePressEvent(self, event) -> None:
        if self._in_press:
            return
        self._in_press = True
        try:
            if event.button() == Qt.MouseButton.LeftButton:
                self.clicked.emit(event.pos())
                event.accept()
        finally:
            self._in_press = False


class HoverButton(QWidget):
    """Simple hover button for panels."""

    def __init__(self, title: str, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setObjectName("hoverButton")
        self._callback: Optional[Callable] = None
        self._label = QLabel(title, self)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.addWidget(self._label)

    def set_click_callback(self, callback: Callable) -> None:
        self._callback = callback

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._callback:
            try:
                self._callback()
            except Exception as e:
                logger.error(f"Button callback error: {e}")
        event.accept()


class SettingsRootPanel(QFrame):
    """Root settings panel."""

    def __init__(self, parent: QWidget, icons):
        super().__init__(parent)
        self.setObjectName("settingsRootPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._icons = icons
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.btn_theme = HoverButton("Theme")
        self.btn_info = HoverButton("Information")
        layout.addWidget(self.btn_theme)
        layout.addWidget(self.btn_info)
        self.setFixedWidth(220)
        self.hide()

    def update_icons(self) -> None:
        """Update icons (no-op for simple buttons)."""
        pass


class ThemeSubPanel(QFrame):
    """Theme selection sub-panel."""

    def __init__(self, parent: QWidget):
        super().__init__(parent)
        self.setObjectName("themeSubPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(2)
        self.btn_light = HoverButton("Light")
        self.btn_dark = HoverButton("Dark")
        layout.addWidget(self.btn_light)
        layout.addWidget(self.btn_dark)
        self.setFixedWidth(100)
        self.hide()
