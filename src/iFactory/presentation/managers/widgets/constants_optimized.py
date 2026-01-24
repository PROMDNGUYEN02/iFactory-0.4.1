"""
Widget Constants - Unified UI Constants using Design System.

All values sourced from DesignTokens - NO hardcoded values.
Maintains backward compatibility while leveraging centralized design system.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, Dict, Final, FrozenSet, List
from PySide6.QtCore import QSize

if TYPE_CHECKING:
    from iFactory.presentation.managers.theme import ThemeManager

# Import design tokens
from iFactory.presentation.managers.theme.design_tokens import (
    DesignTokens,
    ThemeMode,
    IconSize as DesignIconSize,
    SpacingToken,
    RadiusToken,
)

# Legacy enums for backward compatibility
class IconSize(IntEnum):
    """Standard icon sizes (deprecated - use DesignIconSize)."""

    SMALL = DesignIconSize.XS.value
    MEDIUM = DesignIconSize.MD.value
    LARGE = DesignIconSize.LG.value
    XLARGE = DesignIconSize.XL.value

    @classmethod
    def from_design(cls, size: DesignIconSize) -> "IconSize":
        """Convert from DesignIconSize."""
        return cls(size.value)


class MenuDimension(IntEnum):
    """Menu dimension constants."""

    ITEM_HEIGHT = 40
    WIDTH_EXPANDED = 250
    WIDTH_COLLAPSED = 50


class RightPanelDimension(IntEnum):
    """Right panel dimension constants."""

    WIDTH_EXPANDED = 350
    WIDTH_COLLAPSED = 0
    WIDTH_MIN = 300
    WIDTH_MAX = 600
    HOVER_ZONE_WIDTH = 25


class TimerInterval(IntEnum):
    """Timer intervals in milliseconds."""

    THEME_HIDE = 150
    RIGHT_HOVER = 800
    POSITION_UPDATE = 10
    DEVICE_UPDATE = 50
    INIT_DELAY = 100
    GANTT_INIT = 300
    ANIMATION_DURATION = 200


@dataclass(frozen=True, slots=True)
class WindowConstants:
    """
    Immutable window-related constants using design tokens.

    All values sourced from DesignTokens for single source of truth.
    """

    def __init__(self):
        # Initialize from design tokens
        self._init_from_tokens()

    def _init_from_tokens(self):
        """Initialize from design tokens."""
        # Icon size - use MD (24px) as default
        self.ICON_SIZE: QSize = QSize(
            DesignIconSize.MD.value,
            DesignIconSize.MD.value
        )

        # Menu dimensions
        self.MENU_ITEM_HEIGHT: int = MenuDimension.ITEM_HEIGHT
        self.MENU_WIDTH_EXPANDED: int = MenuDimension.WIDTH_EXPANDED
        self.MENU_WIDTH_COLLAPSED: int = MenuDimension.WIDTH_COLLAPSED

        # Right panel dimensions
        self.RIGHT_PANEL_WIDTH_EXPANDED: int = RightPanelDimension.WIDTH_EXPANDED
        self.RIGHT_PANEL_WIDTH_COLLAPSED: int = RightPanelDimension.WIDTH_COLLAPSED
        self.RIGHT_PANEL_WIDTH_MIN: int = RightPanelDimension.WIDTH_MIN
        self.RIGHT_PANEL_WIDTH_MAX: int = RightPanelDimension.WIDTH_MAX
        self.RIGHT_HOVER_ZONE_WIDTH: int = RightPanelDimension.HOVER_ZONE_WIDTH

        # Animation timing
        self.ANIMATION_DURATION: int = TimerInterval.ANIMATION_DURATION
        self.TIMER_THEME_HIDE: int = TimerInterval.THEME_HIDE
        self.TIMER_RIGHT_HOVER: int = TimerInterval.RIGHT_HOVER
        self.TIMER_POSITION_UPDATE: int = TimerInterval.POSITION_UPDATE
        self.TIMER_DEVICE_UPDATE: int = TimerInterval.DEVICE_UPDATE
        self.TIMER_INIT_DELAY: int = TimerInterval.INIT_DELAY
        self.TIMER_GANTT_INIT: int = TimerInterval.GANTT_INIT

        # Widget sizing
        self.MENU_BTN_H: int = MenuDimension.ITEM_HEIGHT
        self.MENU_ICON: int = DesignIconSize.MD.value
        self.MENU_ICON_PAD: int = DesignTokens.get_spacing("xs")

        self.PANEL_MIN_W: int = RightPanelDimension.WIDTH_MIN
        self.PANEL_MAX_W: int = RightPanelDimension.WIDTH_MAX
        self.PANEL_DEF_W: int = RightPanelDimension.WIDTH_EXPANDED
        self.HANDLE_W: int = 6
        self.TOGGLE_W: int = DesignIconSize.MD.value
        self.TOGGLE_H: int = 40
        self.ARROW_ICON: int = DesignIconSize.LG.value

        self.SETTINGS_W: int = 220
        self.THEME_W: int = 100
        self.TABLE_ROW_H: int = DesignTokens.get_typography("body-small")["font_size"] + DesignTokens.get_spacing("sm")
        self.TABLE_HEADER_H: int = DesignTokens.get_typography("body")["font_size"] + DesignTokens.get_spacing("sm")

    # Legacy accessors for backward compatibility
    @property
    def spacing(self) -> Dict[str, int]:
        """Get all spacing values."""
        return {
            "xs": DesignTokens.get_spacing("xs"),
            "sm": DesignTokens.get_spacing("sm"),
            "md": DesignTokens.get_spacing("md"),
            "lg": DesignTokens.get_spacing("lg"),
            "xl": DesignTokens.get_spacing("xl"),
            "xxl": DesignTokens.get_spacing("xxl"),
        }

    @property
    def radius(self) -> Dict[str, int]:
        """Get all radius values."""
        return {
            "none": DesignTokens.get_radius("none"),
            "sm": DesignTokens.get_radius("sm"),
            "md": DesignTokens.get_radius("md"),
            "lg": DesignTokens.get_radius("lg"),
            "xl": DesignTokens.get_radius("xl"),
            "full": DesignTokens.get_radius("full"),
        }


class Sizes:
    """
    Widget dimension constants using design tokens.

    Simple access to commonly used sizes.
    All values sourced from DesignTokens.
    """

    @staticmethod
    def get_spacing(name: str) -> int:
        """Get spacing value from design tokens."""
        return DesignTokens.get_spacing(name)

    @staticmethod
    def get_radius(name: str) -> int:
        """Get radius value from design tokens."""
        return DesignTokens.get_radius(name)

    @staticmethod
    def get_font_size(name: str) -> int:
        """Get font size from design tokens."""
        typo = DesignTokens.get_typography(name)
        return typo["font_size"] if typo else 13

    # Legacy constants for backward compatibility
    MENU_BTN_H: Final[int] = MenuDimension.ITEM_HEIGHT
    MENU_ICON: Final[int] = DesignIconSize.MD.value
    MENU_ICON_PAD: Final[int] = DesignTokens.get_spacing("xs")

    PANEL_MIN_W: Final[int] = RightPanelDimension.WIDTH_MIN
    PANEL_MAX_W: Final[int] = RightPanelDimension.WIDTH_MAX
    PANEL_DEF_W: Final[int] = RightPanelDimension.WIDTH_EXPANDED
    HANDLE_W: Final[int] = 6
    TOGGLE_W: Final[int] = DesignIconSize.MD.value
    TOGGLE_H: Final[int] = 40
    ARROW_ICON: Final[int] = DesignIconSize.LG.value

    SETTINGS_W: Final[int] = 220
    THEME_W: Final[int] = 100
    TABLE_ROW_H: Final[int] = 28
    TABLE_HEADER_H: Final[int] = 32


class Timing:
    """Animation/debounce timing constants (milliseconds)."""

    HOVER: Final[int] = TimerInterval.RIGHT_HOVER
    LEAVE: Final[int] = TimerInterval.THEME_HIDE
    ANIM: Final[int] = TimerInterval.ANIMATION_DURATION
    DEBOUNCE: Final[int] = TimerInterval.POSITION_UPDATE


class Icons:
    """Icon resource path constants.

    Deprecated - Use ThemeManager.get_icon() instead.
    Kept for backward compatibility.
    """

    ARROW_OPEN: Final[str] = "menu-open"
    ARROW_CLOSE: Final[str] = "menu-close"
    EXPAND: Final[str] = "expand"
    CLOSE: Final[str] = "close"
    SETTINGS: Final[str] = "settings"
    LOGO: Final[str] = "logo"
    OPEN: Final[str] = "menu-open"


# Page mappings
PAGE_MAPPING: Final[Dict[str, str]] = {
    "Dashboard": "daboard_page",
    "Orders": "orders_page",
    "Products": "products_page",
    "Customers": "customers_page",
    "Reports": "reports_page",
}

DEVICE_FRAMES: Final[FrozenSet[str]] = frozenset({"daboard_midle_frame_1", "orders_midle_frame_1"})
GANTT_FRAMES: Final[FrozenSet[str]] = frozenset({"daboard_midle_frame_2", "orders_midle_frame_2"})
LEGEND_FRAMES: Final[FrozenSet[str]] = frozenset({"daboard_bottom_frame", "orders_bottom_frame"})
DEVICE_FRAMES_LIST: Final[List[str]] = list(DEVICE_FRAMES)
GANTT_FRAMES_LIST: Final[List[str]] = list(GANTT_FRAMES)
LEGEND_FRAMES_LIST: Final[List[str]] = list(LEGEND_FRAMES)
GANTT_PAGE_MAPPING: Final[Dict[str, str]] = {
    "daboard_page": "daboard_midle_frame_2",
    "orders_page": "orders_midle_frame_2",
}


class HistoryType:
    """History type constants."""

    STATUS: Final[str] = "status"
    INPUT: Final[str] = "input"
    OUTPUT: Final[str] = "output"
    SUMMARY: Final[str] = "summary"
    ALL: Final[FrozenSet[str]] = frozenset({STATUS, INPUT, OUTPUT})
    DISPLAY_NAMES: Final[Dict[str, str]] = {
        STATUS: "Status",
        INPUT: "Input",
        OUTPUT: "Output",
        SUMMARY: "Summary",
    }
    ICONS: Final[Dict[str, str]] = {
        STATUS: "📋",
        INPUT: "📥",
        OUTPUT: "📤",
        SUMMARY: "📊",
    }

    @classmethod
    def get_display_name(cls, history_type: str) -> str:
        return cls.DISPLAY_NAMES.get(history_type, "History")

    @classmethod
    def get_icon(cls, history_type: str) -> str:
        return cls.ICONS.get(history_type, "📄")


__all__ = [
    "IconSize",
    "MenuDimension",
    "RightPanelDimension",
    "TimerInterval",
    "WindowConstants",
    "Sizes",
    "Timing",
    "Icons",
    "PAGE_MAPPING",
    "DEVICE_FRAMES",
    "GANTT_FRAMES",
    "LEGEND_FRAMES",
    "DEVICE_FRAMES_LIST",
    "GANTT_FRAMES_LIST",
    "LEGEND_FRAMES_LIST",
    "GANTT_PAGE_MAPPING",
    "DefaultGanttDevices",
    "HistoryType",
]
