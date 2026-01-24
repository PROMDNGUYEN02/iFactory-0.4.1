"""
Design Tokens - Single Source of Truth for Design System.

Defines all design tokens: colors, spacing, typography, shadows, etc.
Used by ThemeManager for QSS generation and runtime theme switching.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import ClassVar, Dict


class ThemeMode(Enum):
    """Theme mode enumeration."""

    LIGHT = "light"
    DARK = "dark"


class ColorSemantic(Enum):
    """Color semantic categories."""

    PRIMARY = "primary"
    SECONDARY = "secondary"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    INFO = "info"


@dataclass(frozen=True, slots=True)
class ColorToken:
    """Design token for color."""

    name: str
    light: str
    dark: str
    semantic: ColorSemantic | None = None
    description: str = ""

    @property
    def css_var(self) -> str:
        """CSS variable name."""
        return f"--color-{self.name}"


@dataclass(frozen=True, slots=True)
class SpacingToken:
    """Design token for spacing."""

    name: str
    value: int
    description: str = ""

    @property
    def css_var(self) -> str:
        """CSS variable name."""
        return f"--spacing-{self.name}"


@dataclass(frozen=True, slots=True)
class TypographyToken:
    """Design token for typography."""

    name: str
    font_family: str
    font_size: int
    font_weight: int
    line_height: float
    letter_spacing: float
    description: str = ""

    @property
    def css_var(self) -> str:
        """CSS variable name."""
        return f"--typography-{self.name}"


@dataclass(frozen=True, slots=True)
class ShadowToken:
    """Design token for shadows."""

    name: str
    value_light: str
    value_dark: str
    description: str = ""

    @property
    def css_var(self) -> str:
        """CSS variable name."""
        return f"--shadow-{self.name}"


@dataclass(frozen=True, slots=True)
class RadiusToken:
    """Design token for border radius."""

    name: str
    value: int
    description: str = ""

    @property
    def css_var(self) -> str:
        """CSS variable name."""
        return f"--radius-{self.name}"


class DesignTokens:
    """
    Design Tokens - Single source of truth for design system.

    All visual aspects of the application are defined here.
    Tokens are used by ThemeManager to generate CSS variables.

    Categories:
        - Colors: Brand colors, functional colors, semantic colors
        - Spacing: Consistent spacing scale
        - Typography: Font sizes, weights, line heights
        - Shadows: Elevation shadows
        - Radius: Border radius values
    """

    COLOR_TOKENS: ClassVar[Dict[str, ColorToken]] = {
        "primary": ColorToken(
            "primary",
            "#0078D4",
            "#4CC2FF",
            ColorSemantic.PRIMARY,
            "Primary brand color"
        ),
        "primary-hover": ColorToken(
            "primary-hover",
            "#106EBE",
            "#7BD0FF",
            ColorSemantic.PRIMARY,
            "Primary hover state"
        ),
        "primary-active": ColorToken(
            "primary-active",
            "#005A9E",
            "#0095F2",
            ColorSemantic.PRIMARY,
            "Primary active/pressed state"
        ),
        "secondary": ColorToken(
            "secondary",
            "#6C757D",
            "#A0A0A0",
            ColorSemantic.SECONDARY,
            "Secondary text color"
        ),
        "success": ColorToken(
            "success",
            "#107C10",
            "#4CAF50",
            ColorSemantic.SUCCESS,
            "Success/safe state color"
        ),
        "warning": ColorToken(
            "warning",
            "#FF8C00",
            "#FFB74D",
            ColorSemantic.WARNING,
            "Warning/caution state color"
        ),
        "error": ColorToken(
            "error",
            "#D13438",
            "#EF5350",
            ColorSemantic.ERROR,
            "Error/danger state color"
        ),
        "info": ColorToken(
            "info",
            "#0078D4",
            "#4CC2FF",
            ColorSemantic.INFO,
            "Information state color"
        ),
        "background": ColorToken(
            "background",
            "#FFFFFF",
            "#1E1E1E",
            None,
            "Primary background"
        ),
        "surface": ColorToken(
            "surface",
            "#F5F5F5",
            "#2D2D2D",
            None,
            "Secondary/surface background"
        ),
        "surface-hover": ColorToken(
            "surface-hover",
            "#E8E8E8",
            "#3D3D3D",
            None,
            "Surface hover state"
        ),
        "surface-active": ColorToken(
            "surface-active",
            "#D9D9D9",
            "#4D4D4D",
            None,
            "Surface active/pressed state"
        ),
        "text-primary": ColorToken(
            "text-primary",
            "#323130",
            "#FFFFFF",
            None,
            "Primary text color"
        ),
        "text-secondary": ColorToken(
            "text-secondary",
            "#605E5C",
            "#CCCCCC",
            None,
            "Secondary text color"
        ),
        "text-tertiary": ColorToken(
            "text-tertiary",
            "#A19F9D",
            "#999999",
            None,
            "Tertiary text color"
        ),
        "text-disabled": ColorToken(
            "text-disabled",
            "#D1D1D1",
            "#666666",
            None,
            "Disabled text color"
        ),
        "border": ColorToken(
            "border",
            "#E1DFDD",
            "#444444",
            None,
            "Default border color"
        ),
        "border-light": ColorToken(
            "border-light",
            "#F0F0F0",
            "#333333",
            None,
            "Light border color"
        ),
        "border-focus": ColorToken(
            "border-focus",
            "#0078D4",
            "#4CC2FF",
            None,
            "Focus ring color"
        ),
        "divider": ColorToken(
            "divider",
            "#E0E0E0",
            "#3D3D3D",
            None,
            "Divider line color"
        ),
        "overlay": ColorToken(
            "overlay",
            "rgba(0, 0, 0, 0.4)",
            "rgba(0, 0, 0, 0.6)",
            None,
            "Modal/overlay background"
        ),
        "status-running": ColorToken(
            "status-running",
            "#4CAF50",
            "#66BB6A",
            ColorSemantic.SUCCESS,
            "Device running status"
        ),
        "status-shutdown": ColorToken(
            "status-shutdown",
            "#9E9E9E",
            "#757575",
            None,
            "Device shutdown status"
        ),
        "status-stop": ColorToken(
            "status-stop",
            "#F44336",
            "#EF5350",
            ColorSemantic.ERROR,
            "Device stopped status"
        ),
        "status-maintenance": ColorToken(
            "status-maintenance",
            "#2196F3",
            "#42A5F5",
            ColorSemantic.INFO,
            "Device maintenance status"
        ),
        "status-alarm": ColorToken(
            "status-alarm",
            "#FF9800",
            "#FFA726",
            ColorSemantic.WARNING,
            "Device alarm status"
        ),
        "status-unknown": ColorToken(
            "status-unknown",
            "#9E9E9E",
            "#757575",
            None,
            "Device unknown status"
        ),
    }

    SPACING_TOKENS: ClassVar[Dict[str, SpacingToken]] = {
        "xs": SpacingToken("xs", 4, "Extra small spacing"),
        "sm": SpacingToken("sm", 8, "Small spacing"),
        "md": SpacingToken("md", 16, "Medium spacing"),
        "lg": SpacingToken("lg", 24, "Large spacing"),
        "xl": SpacingToken("xl", 32, "Extra large spacing"),
        "xxl": SpacingToken("xxl", 48, "Extra extra large spacing"),
    }

    TYPOGRAPHY_TOKENS: ClassVar[Dict[str, TypographyToken]] = {
        "caption": TypographyToken(
            "caption",
            "Segoe UI",
            11,
            400,
            1.4,
            0.0,
            "Caption text"
        ),
        "body-small": TypographyToken(
            "body-small",
            "Segoe UI",
            12,
            400,
            1.5,
            0.0,
            "Small body text"
        ),
        "body": TypographyToken(
            "body",
            "Segoe UI",
            13,
            400,
            1.5,
            0.0,
            "Body text"
        ),
        "body-large": TypographyToken(
            "body-large",
            "Segoe UI",
            14,
            400,
            1.5,
            0.0,
            "Large body text"
        ),
        "heading-small": TypographyToken(
            "heading-small",
            "Segoe UI",
            16,
            600,
            1.4,
            -0.01,
            "Small heading"
        ),
        "heading": TypographyToken(
            "heading",
            "Segoe UI",
            18,
            600,
            1.3,
            -0.01,
            "Heading"
        ),
        "heading-large": TypographyToken(
            "heading-large",
            "Segoe UI",
            20,
            600,
            1.3,
            -0.02,
            "Large heading"
        ),
        "display-small": TypographyToken(
            "display-small",
            "Segoe UI",
            24,
            700,
            1.2,
            -0.02,
            "Small display"
        ),
        "display": TypographyToken(
            "display",
            "Segoe UI",
            28,
            700,
            1.2,
            -0.03,
            "Display text"
        ),
        "display-large": TypographyToken(
            "display-large",
            "Segoe UI",
            32,
            700,
            1.1,
            -0.04,
            "Large display"
        ),
    }

    SHADOW_TOKENS: ClassVar[Dict[str, ShadowToken]] = {
        "sm": ShadowToken(
            "sm",
            "0 1px 2px rgba(0, 0, 0, 0.05)",
            "0 1px 2px rgba(0, 0, 0, 0.1)",
            "Small shadow for cards, panels"
        ),
        "md": ShadowToken(
            "md",
            "0 4px 6px rgba(0, 0, 0, 0.07)",
            "0 4px 6px rgba(0, 0, 0, 0.15)",
            "Medium shadow for dropdowns, tooltips"
        ),
        "lg": ShadowToken(
            "lg",
            "0 10px 15px rgba(0, 0, 0, 0.1)",
            "0 10px 15px rgba(0, 0, 0, 0.2)",
            "Large shadow for modals, panels"
        ),
        "xl": ShadowToken(
            "xl",
            "0 20px 25px rgba(0, 0, 0, 0.15)",
            "0 20px 25px rgba(0, 0, 0, 0.3)",
            "Extra large shadow for floating elements"
        ),
        "inner": ShadowToken(
            "inner",
            "inset 0 2px 4px rgba(0, 0, 0, 0.06)",
            "inset 0 2px 4px rgba(0, 0, 0, 0.12)",
            "Inner shadow for pressed states"
        ),
        "focus-ring": ShadowToken(
            "focus-ring",
            "0 0 0 3px rgba(0, 120, 212, 0.3)",
            "0 0 0 3px rgba(76, 194, 255, 0.4)",
            "Focus ring outline"
        ),
    }

    RADIUS_TOKENS: ClassVar[Dict[str, RadiusToken]] = {
        "none": RadiusToken("none", 0, "No radius"),
        "sm": RadiusToken("sm", 2, "Small radius"),
        "md": RadiusToken("md", 4, "Medium radius"),
        "lg": RadiusToken("lg", 8, "Large radius"),
        "xl": RadiusToken("xl", 12, "Extra large radius"),
        "full": RadiusToken("full", 9999, "Full circle radius"),
    }

    @classmethod
    def get_color(cls, name: str, mode: ThemeMode = ThemeMode.LIGHT) -> str:
        """
        Get color value for token name and mode.

        Args:
            name: Color token name (e.g., 'primary', 'error')
            mode: Theme mode

        Returns:
            Color value in hex or rgba format
        """
        token = cls.COLOR_TOKENS.get(name)
        if not token:
            return "#000000"
        return token.dark if mode == ThemeMode.DARK else token.light

    @classmethod
    def get_spacing(cls, name: str) -> int:
        """
        Get spacing value for token name.

        Args:
            name: Spacing token name (e.g., 'sm', 'md', 'lg')

        Returns:
            Spacing value in pixels
        """
        token = cls.SPACING_TOKENS.get(name)
        return token.value if token else 0

    @classmethod
    def get_typography(cls, name: str) -> TypographyToken | None:
        """
        Get typography token.

        Args:
            name: Typography token name

        Returns:
            TypographyToken or None
        """
        return cls.TYPOGRAPHY_TOKENS.get(name)

    @classmethod
    def get_shadow(cls, name: str, mode: ThemeMode = ThemeMode.LIGHT) -> str:
        """
        Get shadow value for token name and mode.

        Args:
            name: Shadow token name
            mode: Theme mode

        Returns:
            Shadow CSS value
        """
        token = cls.SHADOW_TOKENS.get(name)
        if not token:
            return "none"
        return token.value_dark if mode == ThemeMode.DARK else token.value_light

    @classmethod
    def get_radius(cls, name: str) -> int:
        """
        Get radius value for token name.

        Args:
            name: Radius token name

        Returns:
            Radius value in pixels
        """
        token = cls.RADIUS_TOKENS.get(name)
        return token.value if token else 0

    @classmethod
    def get_all_css_variables(cls, mode: ThemeMode = ThemeMode.LIGHT) -> Dict[str, str]:
        """
        Get all CSS variables for specified mode.

        Args:
            mode: Theme mode

        Returns:
            Dictionary of variable name → value
        """
        variables = {}

        for name, token in cls.COLOR_TOKENS.items():
            variables[f"--color-{name}"] = token.dark if mode == ThemeMode.DARK else token.light

        for name, token in cls.SPACING_TOKENS.items():
            variables[f"--spacing-{name}"] = f"{token.value}px"

        for name, token in cls.TYPOGRAPHY_TOKENS.items():
            variables[f"--font-{name}-family"] = token.font_family
            variables[f"--font-{name}-size"] = f"{token.font_size}px"
            variables[f"--font-{name}-weight"] = str(token.font_weight)
            variables[f"--font-{name}-line-height"] = str(token.line_height)
            variables[f"--font-{name}-letter-spacing"] = f"{token.letter_spacing}em"

        for name, token in cls.SHADOW_TOKENS.items():
            variables[f"--shadow-{name}"] = token.value_dark if mode == ThemeMode.DARK else token.value_light

        for name, token in cls.RADIUS_TOKENS.items():
            variables[f"--radius-{name}"] = f"{token.value}px"

        return variables


__all__ = [
    "DesignTokens",
    "ThemeMode",
    "ColorSemantic",
    "ColorToken",
    "SpacingToken",
    "TypographyToken",
    "ShadowToken",
    "RadiusToken",
]
