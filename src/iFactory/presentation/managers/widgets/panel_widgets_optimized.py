"""
Panel Widgets - Optimized using Design System.

All styling uses ThemeManager - NO hardcoded colors or spacing.
Removes duplicate logic from multiple panel implementations.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional, Callable

from PySide6.QtCore import Qt, Signal, QPoint
from PySide6.QtWidgets import (
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
)

if TYPE_CHECKING:
    from iFactory.presentation.managers.theme import ThemeManager

from iFactory.presentation.managers.theme.design_tokens import DesignTokens

logger = logging.getLogger(__name__)
__all__ = [
    "ThemedPanel",
    "SettingsPanel",
    "ThemePanel",
    "OverlayWidget",
]


class ThemedPanel(QFrame):
    """
    Theme-aware panel using design tokens.

    Base class for all panels (settings, theme, etc.).
    Automatically applies theme stylesheet.
    """

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self.setObjectName("themedPanel")
        self.setProperty("frameType", "panel")

        # Apply theme stylesheet
        self.setStyleSheet(self._theme_manager.get_stylesheet())


class SettingsPanel(ThemedPanel):
    """
    Settings panel using ThemeManager.

    Optimized to remove duplicate logic.
    """

    __slots__ = ("_theme_manager", "_theme_callback", "_info_callback")

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(theme_manager, parent)
        self._theme_manager = theme_manager
        self._theme_callback = None
        self._info_callback = None

        layout = QVBoxLayout(self)
        padding = DesignTokens.get_spacing("sm")
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(DesignTokens.get_spacing("xs"))

        # Settings button
        self._btn_theme = QPushButton("Theme")
        self._btn_theme.setObjectName("settingsPanelButton")
        self._btn_theme.setProperty("buttonType", "secondary")
        layout.addWidget(self._btn_theme)

        # Info button
        self._btn_info = QPushButton("Information")
        self._btn_info.setObjectName("settingsPanelButton")
        self._btn_info.setProperty("buttonType", "secondary")
        layout.addWidget(self._btn_info)

        # Apply theme stylesheet
        self.setStyleSheet(self._theme_manager.get_stylesheet())
        self._btn_theme.setStyleSheet(self._theme_manager.get_stylesheet())
        self._btn_info.setStyleSheet(self._theme_manager.get_stylesheet())

    def set_theme_click_callback(self, callback: Callable) -> None:
        """Set theme button click callback."""
        self._theme_callback = callback
        self._btn_theme.clicked.connect(callback)

    def set_info_click_callback(self, callback: Callable) -> None:
        """Set info button click callback."""
        self._info_callback = callback
        self._btn_info.clicked.connect(callback)

    def update_theme_icon(self, icon_name: str) -> None:
        """Update theme button icon."""
        icon = self._theme_manager.get_icon(icon_name)
        self._btn_theme.setIcon(icon)


class ThemePanel(ThemedPanel):
    """
    Theme selection panel using ThemeManager.

    Light/Dark theme selection.
    """

    __slots__ = ("_theme_manager", "_light_callback", "_dark_callback")

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(theme_manager, parent)
        self._theme_manager = theme_manager
        self._light_callback = None
        self._dark_callback = None

        layout = QVBoxLayout(self)
        padding = DesignTokens.get_spacing("sm")
        layout.setContentsMargins(padding, padding, padding, padding)
        layout.setSpacing(DesignTokens.get_spacing("xs"))

        # Light theme button
        self._btn_light = QPushButton("Light")
        self._btn_light.setObjectName("themePanelButton")
        self._btn_light.setProperty("buttonType", "secondary")
        layout.addWidget(self._btn_light)

        # Dark theme button
        self._btn_dark = QPushButton("Dark")
        self._btn_dark.setObjectName("themePanelButton")
        self._btn_dark.setProperty("buttonType", "secondary")
        layout.addWidget(self._btn_dark)

        # Apply theme stylesheet
        self.setStyleSheet(self._theme_manager.get_stylesheet())
        self._btn_light.setStyleSheet(self._theme_manager.get_stylesheet())
        self._btn_dark.setStyleSheet(self._theme_manager.get_stylesheet())

    def set_light_click_callback(self, callback: Callable) -> None:
        """Set light theme button callback."""
        self._light_callback = callback
        self._btn_light.clicked.connect(callback)

    def set_dark_click_callback(self, callback: Callable) -> None:
        """Set dark theme button callback."""
        self._dark_callback = callback
        self._btn_dark.clicked.connect(callback)

    def set_active_theme(self, theme: str) -> None:
        """Set active theme state."""
        active = theme.lower() == "dark"

        self._btn_light.setProperty("buttonType", "primary" if not active else "secondary")
        self._btn_light.style().unpolish(self._btn_light)
        self._btn_light.style().polish(self._btn_light)

        self._btn_dark.setProperty("buttonType", "primary" if active else "secondary")
        self._btn_dark.style().unpolish(self._btn_dark)
        self._btn_dark.style().polish(self._btn_dark)


class OverlayWidget(QWidget):
    """
    Transparent overlay for catching clicks.

    Used to close panels when clicking outside.
    Optimized using design tokens for positioning.
    """

    clicked = Signal(QPoint)

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setObjectName("overlayWidget")

        # Apply theme stylesheet
        self.setStyleSheet("""
            #overlayWidget {
                background-color: var(--color-overlay);
            }
        """)

        self.hide()

    def mousePressEvent(self, event) -> None:
        """Handle click event."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(event.pos())
            event.accept()


class RightPanel(ThemedPanel):
    """
    Right slide panel using ThemeManager.

    Supports content injection and theme switching.
    """

    __slots__ = ("_theme_manager", "_content_widget")

    def __init__(self, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(theme_manager, parent)
        self._theme_manager = theme_manager
        self._content_widget = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(DesignTokens.get_spacing("md"), DesignTokens.get_spacing("md"), DesignTokens.get_spacing("md"), DesignTokens.get_spacing("md"))
        layout.setSpacing(0)

        self.setFixedWidth(RightPanelDimension.WIDTH_EXPANDED)
        self.setProperty("frameType", "right-panel")
        self.setProperty("expanded", "false")

    def set_content(self, widget: QWidget) -> None:
        """Set content widget."""
        if self._content_widget:
            self.layout().removeWidget(self._content_widget)

        self._content_widget = widget
        self.layout().addWidget(widget)

    def set_expanded(self, expanded: bool) -> None:
        """Set expanded state."""
        self.setProperty("expanded", str(expanded).lower())
        self.style().unpolish(self)
        self.style().polish(self)


class RightPanelDimension:
    """Right panel dimension constants."""

    WIDTH_EXPANDED: int = 350
    WIDTH_COLLAPSED: int = 0
    WIDTH_MIN: int = 300
    WIDTH_MAX: int = 600
    HOVER_ZONE_WIDTH: int = 25


class ClickCatcher(OverlayWidget):
    """
    Click catcher widget.

    Alias for OverlayWidget for backward compatibility.
    """

    pass


class HoverButton(QWidget):
    """
    Simple hover button using ThemeManager.

    Removed duplicate logic from panel_widgets.py.
    """

    __slots__ = ("_theme_manager", "_title", "_callback")

    def __init__(self, title: str, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._title = title
        self._callback = None

        layout = QHBoxLayout(self)
        padding = DesignTokens.get_spacing("sm")
        layout.setContentsMargins(padding, 0, padding, 0)
        layout.setSpacing(DesignTokens.get_spacing("xs"))

        label = QLabel(title)
        label.setObjectName("hoverButtonLabel")
        layout.addWidget(label)

        # Apply theme stylesheet
        self.setProperty("buttonType", "secondary")
        self.setStyleSheet(self._theme_manager.get_stylesheet())

    def set_click_callback(self, callback: Callable) -> None:
        """Set click callback."""
        self._callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        """Handle click event."""
        if event.button() == Qt.MouseButton.LeftButton and self._callback:
            try:
                self._callback()
            except Exception as e:
                logger.error(f"Hover button callback error: {e}")
        event.accept()
