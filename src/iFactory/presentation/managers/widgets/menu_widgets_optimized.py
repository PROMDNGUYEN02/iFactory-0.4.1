"""
Menu Widgets - Optimized using Design System.

All styling uses ThemeManager - NO hardcoded colors or spacing.
Removes duplicate logic and improves maintainability.
"""

from __future__ import annotations
import logging
from typing import TYPE_CHECKING, Optional, Callable

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QWidget,
    QLabel,
    QStyledItemDelegate,
    QStyle,
    QStyleOptionViewItem,
    QApplication,
    QHBoxLayout,
    QSizePolicy,
)

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtCore import QModelIndex
    from iFactory.presentation.managers.theme import ThemeManager

from iFactory.presentation.managers.theme.design_tokens import DesignTokens

logger = logging.getLogger(__name__)
__all__ = ["MenuDelegate", "ThemedButton", "ThemedLabel"]


class MenuDelegate(QStyledItemDelegate):
    """
    Optimized menu item delegate using design tokens.

    All styling uses CSS variables from ThemeManager.
    """

    __slots__ = ("_height", "_icon_size")

    def __init__(self, height: int = 40, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._height = height
        self._icon_size = DesignTokens.get_spacing("sm")

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        """Paint menu item using system style."""
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        collapsed = widget and widget.property("collapsed")
        if not collapsed:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
            return

        # Draw background for collapsed state
        bg_opt = QStyleOptionViewItem(opt)
        bg_opt.text = ""
        bg_opt.icon = QIcon()
        bg_opt.features = QStyleOptionViewItem.ViewItemFeature.None_
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, bg_opt, painter, widget)

        # Draw decoration (icon) if present
        decoration = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(decoration, QIcon):
            return

        size = opt.decorationSize if opt.decorationSize.isValid() else QSize(30, 30)
        mode = (
            QIcon.Mode.Disabled
            if not opt.state & QStyle.StateFlag.State_Enabled
            else QIcon.Mode.Active if opt.state & QStyle.StateFlag.State_MouseOver else QIcon.Mode.Normal
        )
        pixmap = decoration.pixmap(size, mode, QIcon.State.Off)

        # Center icon
        inner = opt.rect.adjusted(self._icon_size, 0, -self._icon_size, 0)
        x = inner.x() + (inner.width() - pixmap.width()) // 2
        y = inner.y() + (inner.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        hint = super().sizeHint(option, index)
        hint.setHeight(self._height)
        return hint


class ThemedButton(QWidget):
    """
    Theme-aware button using design tokens.

    Automatically applies theme stylesheet.
    NO hardcoded styles - uses ThemeManager CSS variables.
    """

    __slots__ = ("_label", "_theme_manager")

    def __init__(self, text: str, theme_manager: ThemeManager, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._label = QLabel(text)
        self._label.setObjectName("themedButtonLabel")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._label)

        # Apply theme stylesheet
        self.setStyleSheet(self._theme_manager.get_stylesheet())
        self._label.setStyleSheet(self._theme_manager.get_stylesheet())

    def setText(self, text: str) -> None:
        """Set button text."""
        self._label.setText(text)


class ThemedLabel(QWidget):
    """
    Theme-aware label using design tokens.

    Supports optional icon and action callbacks.
    """

    __slots__ = ("_theme_manager", "_click_callback")

    def __init__(
        self,
        text: str,
        theme_manager: ThemeManager,
        icon_name: str | None = None,
        click_callback: Callable | None = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._click_callback = click_callback

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(DesignTokens.get_spacing("xs"))

        if icon_name and self._theme_manager:
            icon_label = QLabel()
            icon_label.setPixmap(self._theme_manager.get_icon(icon_name))
            layout.addWidget(icon_label)

        text_label = QLabel(text)
        text_label.setObjectName("themedLabelText")
        layout.addWidget(text_label)

        # Apply theme stylesheet
        self.setStyleSheet(self._theme_manager.get_stylesheet())

        if click_callback:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        """Handle click event."""
        if event.button() == Qt.MouseButton.LeftButton and self._click_callback:
            try:
                self._click_callback()
            except Exception as e:
                logger.error(f"Label callback error: {e}")
        event.accept()


class SettingsButton(QWidget):
    """
    Settings button using ThemeManager.

    Optimized to remove duplicate logic from panel_widgets.py.
    """

    __slots__ = ("_theme_manager", "_action_callback", "_icon", "_label")

    def __init__(
        self,
        text: str,
        theme_manager: ThemeManager,
        icon_name: str | None = None,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._action_callback = None

        layout = QHBoxLayout(self)
        padding = DesignTokens.get_spacing("sm")
        layout.setContentsMargins(padding, 0, padding, 0)
        layout.setSpacing(DesignTokens.get_spacing("xs"))

        if icon_name:
            self._icon = QLabel()
            self._icon.setPixmap(theme_manager.get_icon(icon_name))
            layout.addWidget(self._icon)
        else:
            self._icon = None

        self._label = QLabel(text)
        self._label.setObjectName("settingsButtonLabel")
        layout.addWidget(self._label)

        # Apply theme stylesheet with buttonType property
        self.setProperty("buttonType", "secondary")
        self.setStyleSheet(self._theme_manager.get_stylesheet())

    def set_click_callback(self, callback: Callable) -> None:
        """Set click callback."""
        self._action_callback = callback
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def update_icon(self, icon_name: str) -> None:
        """Update icon."""
        if self._icon and self._theme_manager:
            self._icon.setPixmap(self._theme_manager.get_icon(icon_name))

    def mousePressEvent(self, event) -> None:
        """Handle click event."""
        if event.button() == Qt.MouseButton.LeftButton and self._action_callback:
            try:
                self._action_callback()
            except Exception as e:
                logger.error(f"Button callback error: {e}")
        event.accept()


class ThemeButton(QWidget):
    """
    Theme selection button.

    Light/Dark buttons with proper styling.
    """

    __slots__ = ("_theme_manager", "_theme_mode", "_callback")

    def __init__(
        self,
        text: str,
        theme_mode: str,
        theme_manager: ThemeManager,
        callback: Callable,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._theme_manager = theme_manager
        self._theme_mode = theme_mode
        self._callback = callback

        layout = QVBoxLayout(self)
        layout.setContentsMargins(DesignTokens.get_spacing("sm"), 0, DesignTokens.get_spacing("sm"), 0)
        layout.setSpacing(0)

        button = QPushButton(text)
        button.setObjectName("themeSelectionButton")

        # Apply theme-specific styling
        button.setProperty("buttonType", "secondary")
        button.clicked.connect(callback)

        layout.addWidget(button)

        # Apply theme stylesheet
        self.setStyleSheet(self._theme_manager.get_stylesheet())

    def set_active(self, active: bool) -> None:
        """Set active state."""
        button = self.findChild(QPushButton, "themeSelectionButton")
        if button:
            if active:
                button.setProperty("buttonType", "primary")
            else:
                button.setProperty("buttonType", "secondary")
            button.style().unpolish(button)
            button.style().polish(button)
