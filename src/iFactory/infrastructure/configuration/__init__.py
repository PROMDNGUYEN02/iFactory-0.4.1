"""
Infrastructure: Configuration Module.
Exports paths, settings managers, and database configurations.
"""

from .paths import PATHS, AppPaths
from .db_settings import DatabaseConfig
from .settings import SettingsManager, AppSettings, UISettings

__all__ = ["PATHS", "AppPaths", "DatabaseConfig", "SettingsManager", "AppSettings", "UISettings"]
