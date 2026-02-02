# File: presentation/views/components/cards.py
"""
Card components for content containers.

Usage:
    card = Card(theme_service)
    stat_card = StatCard("OEE", "85%", theme_service, color="success")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .base import ThemedFrame
from .progress import AnimatedProgressBar

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class Card(ThemedFrame):
    """
    Basic card container.

    Usage:
        card = Card(theme_service)
        card.layout().addWidget(content)
    """

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            Card {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_lg};
            }}
        """
        )

    def set_padding(self, padding: int) -> None:
        """Set card padding."""
        self._layout.setContentsMargins(padding, padding, padding, padding)

    def set_spacing(self, spacing: int) -> None:
        """Set content spacing."""
        self._layout.setSpacing(spacing)


class ElevatedCard(ThemedFrame):
    """Card with shadow elevation."""

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        # Note: QSS shadows are limited, but we can simulate with border
        self.setStyleSheet(
            f"""
            ElevatedCard {{
                background-color: {tokens.surface_elevated};
                border: 1px solid {tokens.border_subtle};
                border-radius: {tokens.radius_lg};
            }}
        """
        )


class StatCard(ThemedFrame):
    """
    Compact statistics card with value and progress bar.

    Usage:
        card = StatCard("OEE", theme_service, color="success")
        card.set_value("85%", 85.0)
    """

    clicked = Signal()

    def __init__(
        self, title: str, theme_service: "ThemeService", color: str = "primary", parent: Optional[QWidget] = None  # primary, success, warning, error
    ):
        super().__init__(theme_service, parent)
        self._title = title
        self._color = color
        self._color_value = self._get_color_value()

        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _get_color_value(self) -> str:
        """Get color hex value based on color name."""
        tokens = self.tokens
        color_map = {
            "primary": tokens.primary,
            "success": tokens.success,
            "warning": tokens.warning,
            "error": tokens.error,
            "info": tokens.info,
        }
        return color_map.get(self._color, tokens.primary)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Color indicator bar
        self._indicator = QFrame()
        self._indicator.setFixedSize(3, 28)
        layout.addWidget(self._indicator)

        # Content
        content = QVBoxLayout()
        content.setSpacing(4)

        # Title and value row
        row = QHBoxLayout()
        row.setSpacing(8)

        self._title_label = QLabel(self._title)
        row.addWidget(self._title_label)

        self._value_label = QLabel("--")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._value_label)

        content.addLayout(row)

        # Progress bar
        self._progress = AnimatedProgressBar(self._color_value, self._theme_service)
        content.addWidget(self._progress)

        layout.addLayout(content, 1)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self._color_value = self._get_color_value()

        # Card background
        self.setStyleSheet(
            f"""
            StatCard {{
                background: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
            }}
            StatCard:hover {{
                border-color: {tokens.border_strong};
            }}
        """
        )

        # Indicator
        self._indicator.setStyleSheet(
            f"""
            background-color: {self._color_value};
            border-radius: 1px;
        """
        )

        # Labels
        self._title_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

        self._value_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            font-weight: {tokens.font_weight_bold};
            color: {self._color_value};
        """
        )

    def set_value(self, display: str, percent: float) -> None:
        """Set the stat value and progress."""
        self._value_label.setText(display)
        self._progress.animate_to(percent)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class DeviceCard(ThemedFrame):
    """
    Card for displaying device information.

    Usage:
        card = DeviceCard(theme_service)
        card.set_device("AMX01", "Running", "#10B981")
    """

    clicked = Signal(str)  # Emits device_id
    double_clicked = Signal(str)

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._device_id = ""
        self._setup_ui()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(32, 32)
        header.addWidget(self._icon_label)

        self._name_label = QLabel("--")
        self._name_label.setObjectName("device_name")
        header.addWidget(self._name_label, 1)

        self._status_dot = QLabel()
        self._status_dot.setFixedSize(8, 8)
        header.addWidget(self._status_dot)

        layout.addLayout(header)

        # Status label
        self._status_label = QLabel("Unknown")
        self._status_label.setObjectName("device_status")
        layout.addWidget(self._status_label)

    def _apply_theme(self) -> None:
        tokens = self.tokens

        self.setStyleSheet(
            f"""
            DeviceCard {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
            }}
            DeviceCard:hover {{
                border-color: {tokens.primary};
                background-color: {tokens.interactive_hover};
            }}
        """
        )

        self._name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_base};
            font-weight: {tokens.font_weight_semibold};
            color: {tokens.text_primary};
        """
        )

        self._status_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            color: {tokens.text_muted};
        """
        )

    def set_device(self, device_id: str, name: str, status: str, status_color: str, icon_pixmap=None) -> None:
        """Set device information."""
        self._device_id = device_id
        self._name_label.setText(name)
        self._status_label.setText(status)

        # Status dot
        self._status_dot.setStyleSheet(
            f"""
            background-color: {status_color};
            border-radius: 4px;
        """
        )

        # Icon
        if icon_pixmap and not icon_pixmap.isNull():
            self._icon_label.setPixmap(icon_pixmap)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._device_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._device_id)
        super().mouseDoubleClickEvent(event)


__all__ = [
    "Card",
    "ElevatedCard",
    "StatCard",
    "DeviceCard",
]
