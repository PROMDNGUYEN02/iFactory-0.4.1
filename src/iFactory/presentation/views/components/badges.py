# File: presentation/views/components/badges.py
"""
Badge components for status and counts.

Usage:
    badge = StatusBadge("running", theme_service)
    badge = CountBadge(42, theme_service)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from .base import ThemedLabel

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class StatusBadge(ThemedLabel):
    """
    Badge showing machine/device status.

    Usage:
        badge = StatusBadge("running", theme_service)
        badge.set_status("stopped")
    """

    def __init__(self, status: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        self._status = status.lower()
        super().__init__(status.upper(), theme_service, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        color = self._theme_service.get_status_color(self._status)
        bg_color = self._theme_service.get_status_bg_color(self._status)

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg_color};
                color: {color};
                padding: {tokens.space_1} {tokens.space_3};
                border-radius: {tokens.radius_full};
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_semibold};
                text-transform: uppercase;
            }}
        """
        )

    def set_status(self, status: str) -> None:
        """Update the status."""
        self._status = status.lower()
        self.setText(status.upper())
        self._apply_theme()


class StatusDot(QLabel):
    """
    Small colored dot indicating status.

    Usage:
        dot = StatusDot("running", theme_service, size=8)
    """

    def __init__(self, status: str, theme_service: "ThemeService", size: int = 8, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._status = status.lower()
        self._size = size

        self.setFixedSize(size, size)
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        color = self._theme_service.get_status_color(self._status)
        radius = self._size // 2

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {color};
                border-radius: {radius}px;
                min-width: {self._size}px;
                max-width: {self._size}px;
                min-height: {self._size}px;
                max-height: {self._size}px;
            }}
        """
        )

    def set_status(self, status: str) -> None:
        """Update the status."""
        self._status = status.lower()
        self._apply_theme()


class CountBadge(ThemedLabel):
    """
    Badge showing a count value.

    Usage:
        badge = CountBadge(42, theme_service)
        badge.set_count(100)
    """

    def __init__(
        self,
        count: int,
        theme_service: "ThemeService",
        variant: str = "default",  # default, primary, success, warning, error
        parent: Optional[QWidget] = None,
    ):
        self._count = count
        self._variant = variant
        super().__init__(str(count), theme_service, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _apply_theme(self) -> None:
        tokens = self.tokens

        # Get colors based on variant
        if self._variant == "primary":
            bg_color = tokens.primary
            text_color = tokens.text_inverse
        elif self._variant == "success":
            bg_color = tokens.success
            text_color = tokens.text_inverse
        elif self._variant == "warning":
            bg_color = tokens.warning
            text_color = tokens.text_inverse
        elif self._variant == "error":
            bg_color = tokens.error
            text_color = tokens.text_inverse
        else:  # default
            bg_color = tokens.interactive_hover
            text_color = tokens.text_primary

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                padding: {tokens.space_1} {tokens.space_2};
                border-radius: {tokens.radius_full};
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_bold};
                min-width: 18px;
            }}
        """
        )

    def set_count(self, count: int) -> None:
        """Update the count value."""
        self._count = count
        # Format large numbers
        if count >= 1000000:
            self.setText(f"{count / 1000000:.1f}M")
        elif count >= 1000:
            self.setText(f"{count / 1000:.1f}K")
        else:
            self.setText(str(count))


class TextBadge(ThemedLabel):
    """
    Generic text badge with customizable colors.

    Usage:
        badge = TextBadge("NEW", theme_service, variant="primary")
    """

    VARIANTS = {
        "default": ("interactive_hover", "text_primary"),
        "primary": ("primary_subtle", "primary"),
        "success": ("success_subtle", "success"),
        "warning": ("warning_subtle", "warning"),
        "error": ("error_subtle", "error"),
        "info": ("info_subtle", "info"),
    }

    def __init__(self, text: str, theme_service: "ThemeService", variant: str = "default", parent: Optional[QWidget] = None):
        self._variant = variant
        super().__init__(text, theme_service, parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def _apply_theme(self) -> None:
        tokens = self.tokens

        bg_key, text_key = self.VARIANTS.get(self._variant, self.VARIANTS["default"])
        bg_color = getattr(tokens, bg_key, tokens.interactive_hover)
        text_color = getattr(tokens, text_key, tokens.text_primary)

        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg_color};
                color: {text_color};
                padding: {tokens.space_1} {tokens.space_2};
                border-radius: {tokens.radius_sm};
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_medium};
            }}
        """
        )

    def set_variant(self, variant: str) -> None:
        """Change the badge variant."""
        self._variant = variant
        self._apply_theme()


__all__ = [
    "StatusBadge",
    "StatusDot",
    "CountBadge",
    "TextBadge",
]
