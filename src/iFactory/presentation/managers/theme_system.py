"""
Centralized Theme System - Professional Theme Management.

Provides unified theme management across entire application.
Supports:
- Dynamic theme switching
- CSS variable substitution
- Theme-specific resources
- Component-level theme variants
"""

from __future__ import annotations
import json
import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import ClassVar, Dict, Final, Optional

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class ThemeMode(Enum):
    """Theme mode enumeration."""

    LIGHT = "light"
    DARK = "dark"
    AUTO = "auto"


@dataclass(frozen=True, slots=True)
class ThemeColor:
    """Theme color definition."""

    name: str
    value_light: str
    value_dark: str

    def get(self, mode: ThemeMode) -> str:
        """Get color value for theme mode."""
        return self.value_dark if mode == ThemeMode.DARK else self.value_light


@dataclass(frozen=True, slots=True)
class ThemeTypography:
    """Theme typography definition."""

    name: str
    font_size: int
    font_weight: str
    line_height: float


@dataclass(frozen=True, slots=True)
class ThemeSpacing:
    """Theme spacing definition."""

    name: str
    value: int


class ThemeSystem(QObject):
    """
    Centralized Theme System.

    Provides professional theme management with:
    - Dynamic CSS variable substitution
    - Theme-specific resource paths
    - Component-level styling
    - Smooth theme transitions

    Architecture:
        - Single source of truth for all UI styling
        - No hardcoded colors/styles in components
        - Declarative theme definition via JSON
        - Type-safe theme API
    """

    theme_changed = Signal(str)
    variable_changed = Signal(str, str)

    DEFAULT_COLORS: ClassVar[Dict[str, ThemeColor]] = {
        "primary": ThemeColor("primary", "#0078D4", "#4CC2FF"),
        "secondary": ThemeColor("secondary", "#6C757D", "#A0A0A0"),
        "success": ThemeColor("success", "#107C10", "#4CAF50"),
        "warning": ThemeColor("warning", "#FF8C00", "#FFB74D"),
        "error": ThemeColor("error", "#D13438", "#EF5350"),
        "background": ThemeColor("background", "#FFFFFF", "#1E1E1E"),
        "surface": ThemeColor("surface", "#F5F5F5", "#2D2D2D"),
        "text_primary": ThemeColor("text_primary", "#323130", "#FFFFFF"),
        "text_secondary": ThemeColor("text_secondary", "#605E5C", "#CCCCCC"),
        "border": ThemeColor("border", "#E1DFDD", "#444444"),
        "disabled": ThemeColor("disabled", "#A19F9D", "#6D6D6D"),
    }

    DEFAULT_SPACING: ClassVar[Dict[str, ThemeSpacing]] = {
        "xs": ThemeSpacing("xs", 4),
        "sm": ThemeSpacing("sm", 8),
        "md": ThemeSpacing("md", 16),
        "lg": ThemeSpacing("lg", 24),
        "xl": ThemeSpacing("xl", 32),
    }

    DEFAULT_TYPOGRAPHY: ClassVar[Dict[str, ThemeTypography]] = {
        "caption": ThemeTypography("caption", 12, "400", 1.5),
        "body_small": ThemeTypography("body_small", 13, "400", 1.5),
        "body": ThemeTypography("body", 14, "400", 1.5),
        "body_large": ThemeTypography("body_large", 16, "400", 1.5),
        "heading_small": ThemeTypography("heading_small", 18, "600", 1.3),
        "heading": ThemeTypography("heading", 20, "600", 1.3),
        "heading_large": ThemeTypography("heading_large", 24, "600", 1.2),
        "display": ThemeTypography("display", 32, "700", 1.2),
    }

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._mode = ThemeMode.LIGHT
        self._colors: Dict[str, ThemeColor] = self.DEFAULT_COLORS.copy()
        self._spacing: Dict[str, ThemeSpacing] = self.DEFAULT_SPACING.copy()
        self._typography: Dict[str, ThemeTypography] = self.DEFAULT_TYPOGRAPHY.copy()
        self._css_variables: Dict[str, str] = {}
        self._base_css: str = ""
        self._cache: Dict[str, str] = {}
        self._build_css_variables()
        logger.debug("[ThemeSystem] Initialized")

    def set_mode(self, mode: ThemeMode | str) -> None:
        """
        Set theme mode.

        Args:
            mode: ThemeMode enum or string ('light', 'dark', 'auto')
        """
        if isinstance(mode, str):
            mode = ThemeMode(mode.lower())
        self._mode = mode
        self._build_css_variables()
        self._cache.clear()
        self.theme_changed.emit(mode.value)
        logger.info(f"[ThemeSystem] Mode: {mode.value}")

    @property
    def mode(self) -> ThemeMode:
        """Get current theme mode."""
        return self._mode

    @property
    def is_dark(self) -> bool:
        """Check if dark mode is active."""
        return self._mode == ThemeMode.DARK

    def set_color(self, name: str, light: str, dark: str) -> None:
        """
        Set theme color.

        Args:
            name: Color name (e.g., 'primary', 'success')
            light: Light mode value
            dark: Dark mode value
        """
        self._colors[name] = ThemeColor(name, light, dark)
        self._build_css_variables()
        self._cache.clear()
        self.variable_changed.emit(name, light if self._mode == ThemeMode.LIGHT else dark)

    def get_color(self, name: str) -> str:
        """
        Get color value for current mode.

        Args:
            name: Color name

        Returns:
            Color value in hex format
        """
        color = self._colors.get(name)
        return color.get(self._mode) if color else "#000000"

    def get_spacing(self, name: str) -> int:
        """
        Get spacing value.

        Args:
            name: Spacing name (e.g., 'sm', 'md', 'lg')

        Returns:
            Spacing value in pixels
        """
        spacing = self._spacing.get(name)
        return spacing.value if spacing else 0

    def get_font_size(self, name: str) -> int:
        """
        Get font size.

        Args:
            name: Typography name (e.g., 'body', 'heading')

        Returns:
            Font size in pixels
        """
        typography = self._typography.get(name)
        return typography.font_size if typography else 14

    def load_from_file(self, path: Path | str) -> None:
        """
        Load theme from JSON file.

        Args:
            path: Path to theme JSON file
        """
        path = Path(path)
        if not path.exists():
            logger.warning(f"[ThemeSystem] Theme file not found: {path}")
            return

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            self._apply_theme_data(data)
            logger.info(f"[ThemeSystem] Loaded theme from: {path}")
        except Exception as e:
            logger.error(f"[ThemeSystem] Failed to load theme: {e}")

    def _apply_theme_data(self, data: dict) -> None:
        """Apply theme data from dictionary."""
        if "colors" in data:
            for name, color_data in data["colors"].items():
                self._colors[name] = ThemeColor(
                    name,
                    color_data.get("light", "#000000"),
                    color_data.get("dark", "#000000"),
                )

        if "spacing" in data:
            for name, value in data["spacing"].items():
                self._spacing[name] = ThemeSpacing(name, value)

        if "typography" in data:
            for name, typo_data in data["typography"].items():
                self._typography[name] = ThemeTypography(
                    name,
                    typo_data.get("font_size", 14),
                    typo_data.get("font_weight", "400"),
                    typo_data.get("line_height", 1.5),
                )

        self._build_css_variables()
        self._cache.clear()

    def _build_css_variables(self) -> None:
        """Build CSS variables from theme definitions."""
        self._css_variables = {}

        for name, color in self._colors.items():
            self._css_variables[f"color-{name}"] = color.get(self._mode)

        for name, spacing in self._spacing.items():
            self._css_variables[f"spacing-{name}"] = f"{spacing.value}px"

        for name, typography in self._typography.items():
            self._css_variables[f"font-size-{name}"] = f"{typography.font_size}px"
            self._css_variables[f"font-weight-{name}"] = typography.font_weight
            self._css_variables[f"line-height-{name}"] = str(typography.line_height)

    def substitute_css(self, css_template: str) -> str:
        """
        Substitute CSS variables in template.

        Args:
            css_template: CSS template with ${variable} placeholders

        Returns:
            CSS with variables substituted
        """
        pattern = re.compile(r"\$\{([A-Za-z0-9_-]+)\}")

        def replacer(match: re.Match) -> str:
            var_name = match.group(1)
            return self._css_variables.get(var_name, "")

        return pattern.sub(replacer, css_template)

    def render_stylesheet(self, css_template: str) -> str:
        """
        Render stylesheet from template.

        Args:
            css_template: CSS template with ${variable} placeholders

        Returns:
            Rendered stylesheet ready for Qt
        """
        if css_template in self._cache:
            return self._cache[css_template]

        result = self.substitute_css(css_template)
        self._cache[css_template] = result
        return result

    def get_all_variables(self) -> Dict[str, str]:
        """Get all CSS variables for current mode."""
        return self._css_variables.copy()

    def clear_cache(self) -> None:
        """Clear rendered stylesheet cache."""
        self._cache.clear()


__all__ = [
    "ThemeSystem",
    "ThemeMode",
    "ThemeColor",
    "ThemeTypography",
    "ThemeSpacing",
]
