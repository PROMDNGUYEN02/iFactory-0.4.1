# src/iFactory/presentation/views/mixins/themeable.py
"""
Enhanced Themeable Mixin.

Features:
- Skip redundant theme updates
- Transition support
- Style caching
- CSS variable support
"""

from __future__ import annotations

from abc import abstractmethod
from typing import TYPE_CHECKING, Dict, Optional, Protocol, runtime_checkable

from PySide6.QtCore import QPropertyAnimation, QEasingCurve, Slot
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService, ThemeTokens
    from ...viewmodels import ShellViewModel

import logging

logger = logging.getLogger(__name__)


@runtime_checkable
class ThemeableView(Protocol):
    """Protocol for themeable views."""

    def apply_theme(self, theme: str) -> None:
        """Apply theme styling."""
        ...


class ThemeableMixin:
    """
    Mixin that provides consistent theme handling.

    Features:
    - Tracks current theme to skip redundant updates
    - Style caching for performance
    - Transition animations (optional)
    - CSS variable support

    Usage:
        class MyView(QWidget, ThemeableMixin):
            def __init__(self, shell_vm: ShellViewModel):
                super().__init__()
                self._init_theme(shell_vm)

            def _apply_theme_styles(self) -> None:
                tokens = self._theme_service.tokens
                self.setStyleSheet(f'''
                    background-color: {tokens.surface_card};
                    color: {tokens.text_primary};
                ''')
    """

    _theme_service: "ThemeService"
    _current_theme: str
    _style_cache: Dict[str, str]
    _transition_enabled: bool

    def _init_theme(
        self,
        shell_vm: "ShellViewModel",
        enable_transitions: bool = False,
    ) -> None:
        """
        Initialize theme handling.

        Args:
            shell_vm: Shell ViewModel with theme service
            enable_transitions: Enable smooth theme transitions
        """
        self._theme_service = shell_vm.theme_service
        self._current_theme = self._theme_service.current_theme
        self._style_cache = {}
        self._transition_enabled = enable_transitions

        # Bind to theme changes
        shell_vm.themeChanged.connect(self._on_theme_changed_internal)

        # Apply initial theme
        self._apply_theme_styles()

    def _init_theme_direct(
        self,
        theme_service: "ThemeService",
        enable_transitions: bool = False,
    ) -> None:
        """
        Initialize theme handling directly with service.

        Use when ShellViewModel is not available.
        """
        self._theme_service = theme_service
        self._current_theme = theme_service.current_theme
        self._style_cache = {}
        self._transition_enabled = enable_transitions

        theme_service.themeChanged.connect(self._on_theme_changed_internal)
        self._apply_theme_styles()

    @Slot(str)
    def _on_theme_changed_internal(self, theme: str) -> None:
        """Handle theme change - OPTIMIZED to skip redundant updates."""
        if theme == self._current_theme:
            return  # Skip if no change

        old_theme = self._current_theme
        self._current_theme = theme

        # Clear style cache on theme change
        self._style_cache.clear()

        # Apply with optional transition
        if self._transition_enabled and isinstance(self, QWidget):
            self._apply_with_transition()
        else:
            self._apply_theme_styles()

    def _apply_with_transition(self) -> None:
        """Apply theme with fade transition."""
        if not isinstance(self, QWidget):
            self._apply_theme_styles()
            return

        # Simple opacity transition
        widget: QWidget = self

        # Create animation
        animation = QPropertyAnimation(widget, b"windowOpacity")
        animation.setDuration(150)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        # Fade out
        animation.setStartValue(1.0)
        animation.setEndValue(0.95)

        def apply_and_fade_in():
            self._apply_theme_styles()
            # Fade back in
            fade_in = QPropertyAnimation(widget, b"windowOpacity")
            fade_in.setDuration(150)
            fade_in.setStartValue(0.95)
            fade_in.setEndValue(1.0)
            fade_in.start()

        animation.finished.connect(apply_and_fade_in)
        animation.start()

    @abstractmethod
    def _apply_theme_styles(self) -> None:
        """
        Apply theme-specific styles.

        Override in subclasses. Use self._theme_service.tokens for colors.
        """
        raise NotImplementedError("Subclasses must implement _apply_theme_styles")

    @property
    def is_dark(self) -> bool:
        """Check if current theme is dark."""
        return self._current_theme == "dark"

    @property
    def tokens(self) -> "ThemeTokens":
        """Get current theme tokens."""
        return self._theme_service.tokens

    def _get_cached_style(self, key: str, generator: callable) -> str:
        """
        Get cached style or generate new one.

        Usage:
            style = self._get_cached_style("button", self._generate_button_style)
        """
        if key not in self._style_cache:
            self._style_cache[key] = generator()
        return self._style_cache[key]

    def _clear_style_cache(self) -> None:
        """Clear style cache (call when styles need regeneration)."""
        self._style_cache.clear()


class ThemeableFrameMixin(ThemeableMixin):
    """
    Specialized mixin for frame-like containers.

    Provides common frame styling helpers.
    """

    def _apply_frame_style(
        self,
        background: Optional[str] = None,
        border: Optional[str] = None,
        border_radius: int = 0,
        padding: int = 0,
    ) -> str:
        """Generate frame stylesheet."""
        tokens = self._theme_service.tokens

        bg = background or tokens.surface_card
        border_style = border or f"1px solid {tokens.border_default}"

        return f"""
            QFrame {{
                background-color: {bg};
                border: {border_style};
                border-radius: {border_radius}px;
                padding: {padding}px;
            }}
        """


class ThemeableButtonMixin(ThemeableMixin):
    """
    Specialized mixin for button styling.

    Provides common button styling helpers.
    """

    def _apply_button_style(
        self,
        variant: str = "primary",
        size: str = "medium",
    ) -> str:
        """Generate button stylesheet."""
        tokens = self._theme_service.tokens

        # Size configurations
        sizes = {
            "small": {"height": 28, "padding": "4px 12px", "font": 12},
            "medium": {"height": 36, "padding": "8px 16px", "font": 14},
            "large": {"height": 44, "padding": "12px 24px", "font": 16},
        }

        # Variant configurations
        variants = {
            "primary": {
                "bg": tokens.primary,
                "text": "#FFFFFF",
                "hover": tokens.primary_hover if hasattr(tokens, "primary_hover") else tokens.primary,
            },
            "secondary": {
                "bg": tokens.surface_elevated,
                "text": tokens.text_primary,
                "hover": tokens.surface_hover if hasattr(tokens, "surface_hover") else tokens.surface_elevated,
            },
            "ghost": {
                "bg": "transparent",
                "text": tokens.text_primary,
                "hover": tokens.surface_hover if hasattr(tokens, "surface_hover") else tokens.surface_card,
            },
        }

        s = sizes.get(size, sizes["medium"])
        v = variants.get(variant, variants["primary"])

        return f"""
            QPushButton {{
                background-color: {v['bg']};
                color: {v['text']};
                border: none;
                border-radius: 6px;
                height: {s['height']}px;
                padding: {s['padding']};
                font-size: {s['font']}px;
            }}
            QPushButton:hover {{
                background-color: {v['hover']};
            }}
            QPushButton:pressed {{
                opacity: 0.8;
            }}
            QPushButton:disabled {{
                opacity: 0.5;
            }}
        """


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    "ThemeableMixin",
    "ThemeableView",
    "ThemeableFrameMixin",
    "ThemeableButtonMixin",
]
