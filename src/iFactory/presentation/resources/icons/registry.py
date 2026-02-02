# File: presentation/resources/icons/registry.py
"""
Icon Registry - Centralized icon definitions.

Provides:
- Type-safe icon enumeration
- Category organization
- Metadata for each icon
- Theme variant detection
"""

from __future__ import annotations

from enum import Enum, auto
from dataclasses import dataclass
from typing import Optional, Set, List


class IconCategory(Enum):
    """Icon categories for organization and batch operations."""

    NAVIGATION = auto()  # Dashboard, Orders, Settings
    ACTION = auto()  # Close, Expand, Toggle
    STATUS = auto()  # Info, Warning, Error
    DEVICE = auto()  # Machine/equipment icons
    CALENDAR = auto()  # Date range icons
    WINDOW = auto()  # Window controls


@dataclass(frozen=True)
class IconDefinition:
    """
    Immutable icon definition.

    Attributes:
        base_name: Icon file name without extension or theme suffix
        category: Icon category for grouping
        has_themed_variant: Whether icon has a -white variant for dark mode
        subfolder: Optional subfolder within /icon/
        extension: File extension (default: svg)
        description: Optional description for documentation
    """

    base_name: str
    category: IconCategory
    has_themed_variant: bool = True
    subfolder: Optional[str] = None
    extension: str = "svg"
    description: str = ""

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

    def get_path(self, is_dark: bool) -> str:
        """Get path for specified theme."""
        if is_dark and self.has_themed_variant:
            return self.dark_path
        return self.light_path


class Icons(Enum):
    """
    Centralized icon enumeration for application icons.

    Usage:
        from presentation.resources.icons import Icons

        icon = Icons.DASHBOARD
        path = icon.value.light_path  # ":/icon/dashboard.svg"
        dark_path = icon.value.dark_path  # ":/icon/dashboard-white.svg"

        # Get all navigation icons
        nav_icons = Icons.navigation_icons()
    """

    # === NAVIGATION ===
    DASHBOARD = IconDefinition("dashboard", IconCategory.NAVIGATION, description="Main dashboard view")
    ORDERS = IconDefinition("orders", IconCategory.NAVIGATION, description="Orders/Analytics view")
    CUSTOMERS = IconDefinition("customers", IconCategory.NAVIGATION, description="Customer management")
    PRODUCTS = IconDefinition("products", IconCategory.NAVIGATION, description="Product catalog")
    REPORTS = IconDefinition("reports", IconCategory.NAVIGATION, description="Reports and exports")
    SETTINGS = IconDefinition("settings", IconCategory.NAVIGATION, description="Application settings")

    # === LAYOUT ===
    DASHBOARD_LAYOUT = IconDefinition("dashboard_layout", IconCategory.NAVIGATION, description="Dashboard background layout")
    ORDERS_LAYOUT = IconDefinition("orders_layout", IconCategory.NAVIGATION, description="Orders background layout")

    # === PANEL CONTROLS ===
    LEFT_PANEL_OPEN = IconDefinition("left_panel_open", IconCategory.ACTION, description="Expand sidebar")
    LEFT_PANEL_CLOSE = IconDefinition("left_panel_close", IconCategory.ACTION, description="Collapse sidebar")
    ARROW_MENU_OPEN = IconDefinition("arrow_menu_open", IconCategory.ACTION, description="Open menu arrow")
    ARROW_MENU_CLOSE = IconDefinition("arrow_menu_close", IconCategory.ACTION, description="Close menu arrow")

    # === WINDOW CONTROLS ===
    CLOSE = IconDefinition("close", IconCategory.WINDOW, description="Close window/panel")
    EXPAND = IconDefinition("expand", IconCategory.WINDOW, description="Expand/maximize")

    # === THEME ===
    SUN = IconDefinition("sun", IconCategory.ACTION, has_themed_variant=False, description="Light mode indicator")
    MOON = IconDefinition("moon", IconCategory.ACTION, has_themed_variant=False, description="Dark mode indicator")

    # === CALENDAR ===
    CALENDAR_TODAY = IconDefinition("calendar_today", IconCategory.CALENDAR, has_themed_variant=False, description="Today's date")
    CALENDAR_WEEK = IconDefinition("calendar_week", IconCategory.CALENDAR, has_themed_variant=False, description="Week view")
    CALENDAR_MONTH = IconDefinition("calendar_month", IconCategory.CALENDAR, has_themed_variant=False, description="Month view")
    CALENDAR_RANGE = IconDefinition("calendar_range", IconCategory.CALENDAR, has_themed_variant=False, description="Date range picker")
    CALENDAR_YEAR = IconDefinition("calendar_year", IconCategory.CALENDAR, has_themed_variant=False, description="Year view")

    # === STATUS ===
    INFO = IconDefinition("info", IconCategory.STATUS, has_themed_variant=False, description="Information indicator")

    # === BRANDING ===
    LOGO = IconDefinition("logo", IconCategory.NAVIGATION, has_themed_variant=False, extension="png", description="Application logo")

    # =========================================================================
    # Accessors
    # =========================================================================

    @property
    def definition(self) -> IconDefinition:
        """Get the icon definition."""
        return self.value

    @property
    def light_path(self) -> str:
        """Shortcut to get light theme path."""
        return self.value.light_path

    @property
    def dark_path(self) -> str:
        """Shortcut to get dark theme path."""
        return self.value.dark_path

    def get_path(self, is_dark: bool) -> str:
        """Get path for specified theme."""
        return self.value.get_path(is_dark)

    # =========================================================================
    # Class Methods
    # =========================================================================

    @classmethod
    def by_category(cls, category: IconCategory) -> List["Icons"]:
        """Get all icons in a category."""
        return [icon for icon in cls if icon.value.category == category]

    @classmethod
    def navigation_icons(cls) -> List["Icons"]:
        """Get all navigation icons."""
        return cls.by_category(IconCategory.NAVIGATION)

    @classmethod
    def action_icons(cls) -> List["Icons"]:
        """Get all action icons."""
        return cls.by_category(IconCategory.ACTION)

    @classmethod
    def window_icons(cls) -> List["Icons"]:
        """Get all window control icons."""
        return cls.by_category(IconCategory.WINDOW)

    @classmethod
    def calendar_icons(cls) -> List["Icons"]:
        """Get all calendar icons."""
        return cls.by_category(IconCategory.CALENDAR)

    @classmethod
    def themed_icons(cls) -> List["Icons"]:
        """Get all icons that have themed variants."""
        return [icon for icon in cls if icon.value.has_themed_variant]

    @classmethod
    def unthemed_icons(cls) -> List["Icons"]:
        """Get all icons without themed variants."""
        return [icon for icon in cls if not icon.value.has_themed_variant]


class DeviceIcons(Enum):
    """
    Device-specific icons for factory equipment.

    All device icons:
    - Are located in :/icon/devices/
    - Have both light (.svg) and dark (-white.svg) variants
    - Use 3-character equipment codes as base names

    Usage:
        icon = DeviceIcons.ACL
        icon = DeviceIcons.from_code("ACL")
        all_codes = DeviceIcons.all_codes()
    """

    # Equipment icons (alphabetically sorted)
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

    # =========================================================================
    # Accessors
    # =========================================================================

    @property
    def definition(self) -> IconDefinition:
        """Get the icon definition."""
        return self.value

    @property
    def code(self) -> str:
        """Get the equipment code."""
        return self.value.base_name

    @property
    def light_path(self) -> str:
        """Shortcut to get light theme path."""
        return self.value.light_path

    @property
    def dark_path(self) -> str:
        """Shortcut to get dark theme path."""
        return self.value.dark_path

    def get_path(self, is_dark: bool) -> str:
        """Get path for specified theme."""
        return self.value.get_path(is_dark)

    # =========================================================================
    # Class Methods
    # =========================================================================

    @classmethod
    def from_code(cls, code: str) -> Optional["DeviceIcons"]:
        """
        Get device icon by equipment code.

        Args:
            code: Equipment code (case-insensitive)

        Returns:
            DeviceIcons enum member or None if not found
        """
        try:
            return cls[code.upper()]
        except KeyError:
            return None

    @classmethod
    def all_codes(cls) -> Set[str]:
        """Get all valid device codes."""
        return {icon.name for icon in cls}

    @classmethod
    def exists(cls, code: str) -> bool:
        """Check if a device icon exists for the given code."""
        return cls.from_code(code) is not None

    @classmethod
    def count(cls) -> int:
        """Get total number of device icons."""
        return len(cls)


__all__ = [
    "Icons",
    "DeviceIcons",
    "IconDefinition",
    "IconCategory",
]
