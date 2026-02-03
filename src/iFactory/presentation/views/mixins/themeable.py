# File: presentation/views/mixins/themeable.py
"""
Themeable mixin for views.

OPTIMIZED:
1. Skip redundant theme updates
2. Provides consistent theme handling across all views
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from PySide6.QtCore import Slot

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...viewmodels import ShellViewModel


@runtime_checkable
class ThemeableView(Protocol):
    """Protocol for themeable views."""

    def apply_theme(self, theme: str) -> None:
        """Apply theme styling."""
        ...


class ThemeableMixin:
    """
    Mixin that provides consistent theme handling.

    OPTIMIZED:
    - Tracks current theme to skip redundant updates
    - Provides is_dark property for convenience

    Usage:
        class MyView(ThemeableMixin):
            def __init__(self, shell_vm: ShellViewModel):
                self._init_theme(shell_vm)

            def _apply_theme_styles(self) -> None:
                tokens = self._theme_service.tokens
                # Apply styles using tokens...
    """

    _theme_service: "ThemeService"
    _current_theme: str

    def _init_theme(self, shell_vm: "ShellViewModel") -> None:
        """Initialize theme handling."""
        self._theme_service = shell_vm.theme_service
        self._current_theme = self._theme_service.current_theme

        # Bind to theme changes
        shell_vm.themeChanged.connect(self._on_theme_changed_internal)

        # Apply initial theme
        self._apply_theme_styles()

    @Slot(str)
    def _on_theme_changed_internal(self, theme: str) -> None:
        """Handle theme change - OPTIMIZED to skip redundant updates."""
        if theme == self._current_theme:
            return  # Skip if no change

        self._current_theme = theme
        self._apply_theme_styles()

    def _apply_theme_styles(self) -> None:
        """
        Override to apply theme-specific styles.

        Use self._theme_service.tokens for colors.
        """
        raise NotImplementedError("Subclasses must implement _apply_theme_styles")

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark."""
        return self._current_theme == "dark"


__all__ = ["ThemeableMixin", "ThemeableView"]
