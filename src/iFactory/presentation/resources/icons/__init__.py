# File: presentation/resources/icons/__init__.py
"""
Icon management package.

Usage:
    from presentation.resources.icons import Icons, DeviceIcons
    from presentation.resources.icons import get_icon_provider

    # Get cached icon
    provider = get_icon_provider()
    icon = provider.get_icon(Icons.DASHBOARD)
    pixmap = provider.get_pixmap(Icons.SETTINGS, QSize(32, 32))

    # Device icons
    device_icon = provider.get_device_icon("ACL")
"""

from .registry import Icons, DeviceIcons, IconCategory, IconDefinition
from .provider import IconProvider, get_icon_provider

__all__ = [
    # Registry
    "Icons",
    "DeviceIcons",
    "IconCategory",
    "IconDefinition",
    # Provider
    "IconProvider",
    "get_icon_provider",
]
