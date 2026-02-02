# File: presentation/views/components/base.py
"""
Base components for themed widgets.

All components inherit from ThemedWidget for automatic theme handling.
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Slot
from PySide6.QtWidgets import QWidget, QFrame, QPushButton, QLabel

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService, ThemeTokens


class ThemedWidget(QWidget):
    """
    Base class for themed widgets.

    Provides:
    - Automatic theme change handling
    - Access to ThemeTokens
    - Consistent styling API
    """

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._setup_theme_binding()

    def _setup_theme_binding(self) -> None:
        """Connect to theme changes."""
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        # Apply initial theme
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        self._apply_theme()

    @abstractmethod
    def _apply_theme(self) -> None:
        """Apply current theme styles. Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        """Get current theme tokens."""
        return self._theme_service.tokens

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        return self._theme_service.is_dark


class ThemedFrame(QFrame):
    """Base class for themed frames."""

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens


class ThemedButton(QPushButton):
    """Base class for themed buttons."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._theme_service = theme_service
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens


class ThemedLabel(QLabel):
    """Base class for themed labels."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, parent)
        self._theme_service = theme_service
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens


__all__ = [
    "ThemedWidget",
    "ThemedFrame",
    "ThemedButton",
    "ThemedLabel",
]
