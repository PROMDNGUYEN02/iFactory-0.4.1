# File: presentation/constants/layout.py
"""
Layout Constants - Integrated with Design System.

Uses 8pt grid system for consistent spacing.
"""

from typing import Final


class Spacing:
    """8pt grid spacing system."""

    NONE: Final[int] = 0
    XS: Final[int] = 4  # space.1
    SM: Final[int] = 8  # space.2
    MD: Final[int] = 12  # space.3
    BASE: Final[int] = 16  # space.4
    LG: Final[int] = 24  # space.6
    XL: Final[int] = 32  # space.8
    XXL: Final[int] = 48  # space.12


class Radius:
    """Border radius scale."""

    NONE: Final[int] = 0
    SM: Final[int] = 4
    BASE: Final[int] = 6
    MD: Final[int] = 8
    LG: Final[int] = 12
    XL: Final[int] = 16
    FULL: Final[int] = 9999


class IconSize:
    """Icon size scale."""

    SM: Final[int] = 16
    BASE: Final[int] = 20
    MD: Final[int] = 24
    LG: Final[int] = 32
    XL: Final[int] = 48


class ButtonHeight:
    """Button height scale."""

    SM: Final[int] = 28
    BASE: Final[int] = 36
    LG: Final[int] = 44


class Layout:
    """Main layout dimensions."""

    # Sidebar
    SIDEBAR_COLLAPSED_WIDTH: Final[int] = 60
    SIDEBAR_EXPANDED_WIDTH: Final[int] = 220
    SIDEBAR_ANIMATION_DURATION: Final[int] = 200

    # Right Panel
    RIGHT_PANEL_COLLAPSED_WIDTH: Final[int] = 0
    RIGHT_PANEL_EXPANDED_WIDTH: Final[int] = 320
    RIGHT_PANEL_ANIMATION_DURATION: Final[int] = 200

    # Header & Status Bar
    HEADER_HEIGHT: Final[int] = 48
    STATUS_BAR_HEIGHT: Final[int] = 28

    # Gantt Chart
    GANTT_ROW_HEIGHT: Final[int] = 32
    GANTT_COMPACT_ROW_HEIGHT: Final[int] = 20
    GANTT_HEADER_HEIGHT: Final[int] = 40
    GANTT_TIME_SLOT_WIDTH: Final[int] = 60

    # Legend
    LEGEND_HEIGHT: Final[int] = 60

    # Cards
    CARD_MIN_WIDTH: Final[int] = 200
    CARD_MIN_HEIGHT: Final[int] = 120

    # Device Canvas
    DEVICE_CARD_WIDTH: Final[int] = 120
    DEVICE_CARD_HEIGHT: Final[int] = 100
    DEVICE_CARD_SPACING: Final[int] = Spacing.MD


class ZIndex:
    """Z-index layering."""

    BASE: Final[int] = 0
    DROPDOWN: Final[int] = 1000
    STICKY: Final[int] = 1100
    MODAL: Final[int] = 1200
    POPOVER: Final[int] = 1300
    TOOLTIP: Final[int] = 1400


# Backward compatibility alias
SPACING = Spacing
RADIUS = Radius
ICON_SIZE = IconSize


__all__ = [
    "Layout",
    "Spacing",
    "Radius",
    "IconSize",
    "ButtonHeight",
    "ZIndex",
    "SPACING",
    "RADIUS",
    "ICON_SIZE",
]
