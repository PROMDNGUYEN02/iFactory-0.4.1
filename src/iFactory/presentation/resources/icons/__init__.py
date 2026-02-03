# File: presentation/resources/icons/__init__.py
"""
Icon management package.

Provides enum-based, theme-aware icon access with caching.

Usage:
    from presentation.resources.icons import Icons, DeviceIcons, get_icon_provider

    # Get provider
    provider = get_icon_provider()

    # Get cached icon (theme-aware)
    icon = provider.get_icon(Icons.electrode)
    pixmap = provider.get_pixmap(Icons.SETTINGS, QSize(32, 32))

    # Device icons by code
    device_icon = provider.get_device_icon("ACL")
    device_pixmap = provider.get_device_pixmap("CBC", QSize(40, 40))

    # Check available device codes
    all_codes = DeviceIcons.all_codes()
    exists = DeviceIcons.exists("ACL")
"""

from .registry import (
    Icons,
    DeviceIcons,
    IconCategory,
    IconDefinition,
)

from .provider import (
    IconProvider,
    get_icon_provider,
    create_icon_provider,
)

# Note: IconResolver is internal implementation detail
# Use IconProvider.resolve_path() instead

__all__ = [
    # Registry
    "Icons",
    "DeviceIcons",
    "IconCategory",
    "IconDefinition",
    # Provider
    "IconProvider",
    "get_icon_provider",
    "create_icon_provider",
]
