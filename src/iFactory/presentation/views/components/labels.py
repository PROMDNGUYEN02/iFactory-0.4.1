# File: presentation/views/components/labels.py
"""
Label components with consistent typography.

Usage:
    heading = HeadingLabel("Dashboard", theme_service, level=1)
    muted = MutedLabel("Last updated: 10:00", theme_service)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget

from .base import ThemedLabel

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class HeadingLabel(ThemedLabel):
    """
    Heading label with configurable level.

    Levels:
    - 1: Extra large (24px, bold)
    - 2: Large (18px, semibold)
    - 3: Medium (16px, semibold)
    - 4: Base (14px, medium)
    """

    def __init__(self, text: str, theme_service: "ThemeService", level: int = 2, parent: Optional[QWidget] = None):
        self._level = level
        super().__init__(text, theme_service, parent)

    def _apply_theme(self) -> None:
        tokens = self.tokens

        level_styles = {
            1: (tokens.font_size_2xl, tokens.font_weight_bold),
            2: (tokens.font_size_xl, tokens.font_weight_semibold),
            3: (tokens.font_size_lg, tokens.font_weight_semibold),
            4: (tokens.font_size_md, tokens.font_weight_medium),
        }

        size, weight = level_styles.get(self._level, level_styles[2])

        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.text_primary};
                font-size: {size};
                font-weight: {weight};
                background: transparent;
            }}
        """
        )


class SecondaryLabel(ThemedLabel):
    """Label with secondary text color."""

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.text_secondary};
                font-size: {tokens.font_size_base};
                background: transparent;
            }}
        """
        )


class MutedLabel(ThemedLabel):
    """Label with muted/hint text color."""

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.text_muted};
                font-size: {tokens.font_size_sm};
                background: transparent;
            }}
        """
        )


class LinkLabel(ThemedLabel):
    """Clickable link-styled label."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.text_link};
                font-size: {tokens.font_size_base};
                background: transparent;
                text-decoration: underline;
            }}
            QLabel:hover {{
                color: {tokens.text_link_hover};
            }}
        """
        )


class MonoLabel(ThemedLabel):
    """Monospace font label for code/data display."""

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.text_primary};
                font-family: {tokens.font_family_mono};
                font-size: {tokens.font_size_base};
                background: transparent;
            }}
        """
        )


class ErrorLabel(ThemedLabel):
    """Error message label."""

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.error};
                font-size: {tokens.font_size_sm};
                font-weight: {tokens.font_weight_medium};
                background: transparent;
            }}
        """
        )


class SuccessLabel(ThemedLabel):
    """Success message label."""

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QLabel {{
                color: {tokens.success};
                font-size: {tokens.font_size_sm};
                font-weight: {tokens.font_weight_medium};
                background: transparent;
            }}
        """
        )


__all__ = [
    "HeadingLabel",
    "SecondaryLabel",
    "MutedLabel",
    "LinkLabel",
    "MonoLabel",
    "ErrorLabel",
    "SuccessLabel",
]
