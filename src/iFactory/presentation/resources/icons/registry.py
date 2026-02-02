# File: presentation/resources/icons/registry.py
"""
Icon Registry - Centralized icon definitions.

Eliminates:
- Fragile string literals
- Implicit dependencies on SVG filenames
- Typo risks
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Set


class IconCategory(Enum):
    """Icon categories for organization."""

    NAVIGATION = auto()
    ACTION = auto()
    STATUS = auto()
    DEVICE = auto()
    CALENDAR = auto()
    WINDOW = auto()


@dataclass(frozen=True)
class IconDefinition:
    """Immutable icon definition."""

    base_name: str
    category: IconCategory
    has_themed_variant: bool = True
    subfolder: Optional[str] = None
    extension: str = "svg"

    @property
    def resource_path(self) -> str:
        """Get base resource path (without theme suffix)."""
        if self.subfolder:
            return f":/icon/{self.subfolder}/{self.base_name}"
        return f":/icon/{self.base_name}"

    @property
    def light_path(self) -> str:
        """Get path for light theme."""
        return f"{self.resource_path}.{self.extension}"

    @property
    def dark_path(self) -> str:
        """Get path for dark theme (white variant)."""
        if self.has_themed_variant:
            return f"{self.resource_path}-white.{self.extension}"
        return self.light_path


class Icons(Enum):
    """
    Centralized icon enumeration.

    Usage:
        from presentation.resources.icons import Icons

        icon = Icons.DASHBOARD
        path = icon.value.light_path  # ":/icon/dashboard.svg"
    """

    # Navigation icons
    DASHBOARD = IconDefinition("dashboard", IconCategory.NAVIGATION)
    ORDERS = IconDefinition("orders", IconCategory.NAVIGATION)
    CUSTOMERS = IconDefinition("customers", IconCategory.NAVIGATION)
    PRODUCTS = IconDefinition("products", IconCategory.NAVIGATION)
    REPORTS = IconDefinition("reports", IconCategory.NAVIGATION)
    SETTINGS = IconDefinition("settings", IconCategory.NAVIGATION)

    # Layout icons
    DASHBOARD_LAYOUT = IconDefinition("dashboard_layout", IconCategory.NAVIGATION)
    ORDERS_LAYOUT = IconDefinition("orders_layout", IconCategory.NAVIGATION)

    # Panel control icons
    LEFT_PANEL_OPEN = IconDefinition("left_panel_open", IconCategory.ACTION)
    LEFT_PANEL_CLOSE = IconDefinition("left_panel_close", IconCategory.ACTION)
    ARROW_MENU_OPEN = IconDefinition("arrow_menu_open", IconCategory.ACTION)
    ARROW_MENU_CLOSE = IconDefinition("arrow_menu_close", IconCategory.ACTION)

    # Window control icons
    CLOSE = IconDefinition("close", IconCategory.WINDOW)
    EXPAND = IconDefinition("expand", IconCategory.WINDOW)

    # Theme icons (no themed variant - they represent the theme itself)
    SUN = IconDefinition("sun", IconCategory.ACTION, has_themed_variant=False)
    MOON = IconDefinition("moon", IconCategory.ACTION, has_themed_variant=False)

    # Calendar icons
    CALENDAR_TODAY = IconDefinition("calendar_today", IconCategory.CALENDAR, has_themed_variant=False)
    CALENDAR_WEEK = IconDefinition("calendar_week", IconCategory.CALENDAR, has_themed_variant=False)
    CALENDAR_MONTH = IconDefinition("calendar_month", IconCategory.CALENDAR, has_themed_variant=False)
    CALENDAR_RANGE = IconDefinition("calendar_range", IconCategory.CALENDAR, has_themed_variant=False)
    CALENDAR_YEAR = IconDefinition("calendar_year", IconCategory.CALENDAR, has_themed_variant=False)

    # Status icons
    INFO = IconDefinition("info", IconCategory.STATUS, has_themed_variant=False)

    # Logo (PNG, no themed variant)
    LOGO = IconDefinition("logo", IconCategory.NAVIGATION, has_themed_variant=False, extension="png")

    @property
    def definition(self) -> IconDefinition:
        """Get the icon definition."""
        return self.value

    @classmethod
    def by_category(cls, category: IconCategory) -> list["Icons"]:
        """Get all icons in a category."""
        return [icon for icon in cls if icon.value.category == category]

    @classmethod
    def navigation_icons(cls) -> list["Icons"]:
        """Get all navigation icons."""
        return cls.by_category(IconCategory.NAVIGATION)

    @classmethod
    def action_icons(cls) -> list["Icons"]:
        """Get all action icons."""
        return cls.by_category(IconCategory.ACTION)


class DeviceIcons(Enum):
    """
    Device-specific icons.

    All device icons follow the pattern: {CODE}.svg and {CODE}-white.svg
    Located in :/icon/devices/
    """

    ACL = IconDefinition("ACL", IconCategory.DEVICE, subfolder="devices")
    ACT = IconDefinition("ACT", IconCategory.DEVICE, subfolder="devices")
    ALS = IconDefinition("ALS", IconCategory.DEVICE, subfolder="devices")
    AMX = IconDefinition("AMX", IconCategory.DEVICE, subfolder="devices")
    CA1 = IconDefinition("CA1", IconCategory.DEVICE, subfolder="devices")
    CA2 = IconDefinition("CA2", IconCategory.DEVICE, subfolder="devices")
    CAW = IconDefinition("CAW", IconCategory.DEVICE, subfolder="devices")
    CBC = IconDefinition("CBC", IconCategory.DEVICE, subfolder="devices")
    CBD = IconDefinition("CBD", IconCategory.DEVICE, subfolder="devices")
    CBP = IconDefinition("CBP", IconCategory.DEVICE, subfolder="devices")
    CBW = IconDefinition("CBW", IconCategory.DEVICE, subfolder="devices")
    CCI = IconDefinition("CCI", IconCategory.DEVICE, subfolder="devices")
    CCL = IconDefinition("CCL", IconCategory.DEVICE, subfolder="devices")
    CCR = IconDefinition("CCR", IconCategory.DEVICE, subfolder="devices")
    CCT = IconDefinition("CCT", IconCategory.DEVICE, subfolder="devices")
    CCU = IconDefinition("CCU", IconCategory.DEVICE, subfolder="devices")
    CCW = IconDefinition("CCW", IconCategory.DEVICE, subfolder="devices")
    CEJ = IconDefinition("CEJ", IconCategory.DEVICE, subfolder="devices")
    CHW = IconDefinition("CHW", IconCategory.DEVICE, subfolder="devices")
    CJL = IconDefinition("CJL", IconCategory.DEVICE, subfolder="devices")
    CLS = IconDefinition("CLS", IconCategory.DEVICE, subfolder="devices")
    CMX = IconDefinition("CMX", IconCategory.DEVICE, subfolder="devices")
    COC = IconDefinition("COC", IconCategory.DEVICE, subfolder="devices")
    CRB = IconDefinition("CRB", IconCategory.DEVICE, subfolder="devices")
    CSG = IconDefinition("CSG", IconCategory.DEVICE, subfolder="devices")
    CTB = IconDefinition("CTB", IconCategory.DEVICE, subfolder="devices")
    CTI = IconDefinition("CTI", IconCategory.DEVICE, subfolder="devices")
    CWD = IconDefinition("CWD", IconCategory.DEVICE, subfolder="devices")
    CWS = IconDefinition("CWS", IconCategory.DEVICE, subfolder="devices")
    CXI = IconDefinition("CXI", IconCategory.DEVICE, subfolder="devices")

    @property
    def definition(self) -> IconDefinition:
        """Get the icon definition."""
        return self.value

    @classmethod
    def from_code(cls, code: str) -> Optional["DeviceIcons"]:
        """Get device icon by equipment code."""
        try:
            return cls[code.upper()]
        except KeyError:
            return None

    @classmethod
    def all_codes(cls) -> Set[str]:
        """Get all valid device codes."""
        return {icon.name for icon in cls}


__all__ = [
    "Icons",
    "DeviceIcons",
    "IconDefinition",
    "IconCategory",
]
