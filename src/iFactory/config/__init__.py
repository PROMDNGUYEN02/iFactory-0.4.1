"""
Configuration module - Centralized application settings and constants.

This module provides a clean public API for all configuration needs.
Use explicit imports for better IDE support and tree-shaking.

Example:
    >>> from iFactory.config import PATHS, SettingsManager, DeviceStatus
    >>> settings = SettingsManager()
    >>> devices = get_page_devices("dashboard_page")
"""

from __future__ import annotations

__version__ = "0.5.0"
from .settings import (
    PATHS,
    AppPaths,
    PROJECT_ROOT,
    PACKAGE_ROOT,
    DATA_DIR,
    THEME_BASE_PATH,
    THEME_VARS_PATH,
)
from .settings import APP_TITLE, APP_VERSION, APP_NAME
from .settings import (
    QtIcons,
    MenuItem,
    MenuItems,
    DatabaseConfig,
    APP_ICON_PATH,
    ICON_LOGO,
    ICON_OPEN,
    ICON_CLOSE,
    ICON_SETTINGS,
    ICON_EXPAND,
    ICON_ARROW_OPEN,
    ICON_ARROW_CLOSE,
)
from .constants import (
    DeviceStatus,
    StatusDisplay,
    ThemeMode,
    StatusColors,
    get_status_color,
    TimeConstants,
    Limits,
    UIDefaults,
)
from .settings_manager import SettingsManager, DBSettings, AppSettings, UISettings
from .device_config import DeviceConfigLoader, get_page_devices, get_all_page_devices
from .logging_config import setup_logging, get_logger
from .settings import MSSQL_DRIVERS, detect_available_mssql_driver

__all__ = [
    "__version__",
    "APP_TITLE",
    "APP_VERSION",
    "APP_NAME",
    "PATHS",
    "AppPaths",
    "PROJECT_ROOT",
    "PACKAGE_ROOT",
    "DATA_DIR",
    "THEME_BASE_PATH",
    "THEME_VARS_PATH",
    "QtIcons",
    "APP_ICON_PATH",
    "ICON_LOGO",
    "ICON_OPEN",
    "ICON_CLOSE",
    "ICON_SETTINGS",
    "ICON_EXPAND",
    "ICON_ARROW_OPEN",
    "ICON_ARROW_CLOSE",
    "DeviceStatus",
    "StatusDisplay",
    "ThemeMode",
    "StatusColors",
    "get_status_color",
    "TimeConstants",
    "Limits",
    "UIDefaults",
    "SettingsManager",
    "DBSettings",
    "AppSettings",
    "UISettings",
    "DeviceConfigLoader",
    "get_page_devices",
    "get_all_page_devices",
    "setup_logging",
    "get_logger",
    "MenuItem",
    "MenuItems",
    "DatabaseConfig",
    "MSSQL_DRIVERS",
    "detect_available_mssql_driver",
]
