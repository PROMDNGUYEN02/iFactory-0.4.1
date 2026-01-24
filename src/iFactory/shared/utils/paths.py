"""
Path utilities - Unified path management.

All data files (databases, configs, settings) should be in:
    PROJECT_ROOT/data/

Resources (themes, icons) are in:
    src/iFactory/resources/
"""

from __future__ import annotations
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)
__all__ = [
    "get_package_root",
    "get_src_root",
    "get_project_root",
    "get_resource_path",
    "get_data_path",
    "get_theme_path",
    "get_icon_path",
    "ensure_data_directories",
    "PATHS",
]


@lru_cache(maxsize=1)
def get_package_root() -> Path:
    """
    Get iFactory package root.

    Returns:
        Path to: .../src/iFactory/
    """
    return Path(__file__).parent.parent.parent.resolve()


@lru_cache(maxsize=1)
def get_src_root() -> Path:
    """
    Get src directory.

    Returns:
        Path to: .../src/
    """
    return get_package_root().parent


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """
    Get project root directory.

    Returns:
        Path to project root (parent of src)
    """
    return get_src_root().parent


def get_resource_path(relative_path: str = "") -> Path:
    """
    Get path to resource file/directory.

    Args:
        relative_path: Path relative to resources/

    Example:
        get_resource_path("themes/base.qss")
    """
    base = get_package_root() / "resources"
    return base / relative_path if relative_path else base


def get_data_path(relative_path: str = "") -> Path:
    """
    Get path to data file/directory.

    Data directory is ALWAYS at project root level: PROJECT_ROOT/data/

    Args:
        relative_path: Path relative to data/

    Example:
        get_data_path("settings.json")
        get_data_path("hot_store.db")
    """
    root_data = get_project_root() / "data"
    root_data.mkdir(parents=True, exist_ok=True)
    return root_data / relative_path if relative_path else root_data


def get_theme_path(filename: str) -> Path:
    """Get path to theme file."""
    return get_resource_path(f"themes/{filename}")


def get_icon_path(icon_name: str) -> Path:
    """Get path to icon file."""
    return get_resource_path(f"icon/{icon_name}")


def ensure_data_directories() -> None:
    """Create required data directories."""
    data_dir = get_data_path()
    data_dir.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Data directory ensured: {data_dir}")


class PathsConfig:
    """
    Centralized paths configuration.

    All paths are resolved lazily and cached.
    """

    @property
    def project_root(self) -> Path:
        """Project root directory."""
        return get_project_root()

    @property
    def src_root(self) -> Path:
        """Source directory."""
        return get_src_root()

    @property
    def package_root(self) -> Path:
        """Package root (src/iFactory)."""
        return get_package_root()

    @property
    def data_dir(self) -> Path:
        """Main data directory (PROJECT_ROOT/data/)."""
        path = get_project_root() / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def hot_store_path(self) -> Path:
        """Path to hot store database (real-time data)."""
        return self.data_dir / "hot_store.db"

    @property
    def cold_store_path(self) -> Path:
        """Path to cold store database (historical data)."""
        return self.data_dir / "cold_store.db"

    @property
    def settings_path(self) -> Path:
        """Path to settings.json."""
        return self.data_dir / "settings.json"

    @property
    def device_positions_path(self) -> Path:
        """Path to device_positions.json."""
        return self.data_dir / "device_positions.json"

    @property
    def legends_path(self) -> Path:
        """Path to legends.json."""
        return self.data_dir / "legends.json"

    @property
    def resources_dir(self) -> Path:
        """Resources directory."""
        return get_package_root() / "resources"

    @property
    def themes_dir(self) -> Path:
        """Themes directory."""
        return self.resources_dir / "themes"

    @property
    def icons_dir(self) -> Path:
        """Icons directory."""
        return self.resources_dir / "icon"

    @property
    def theme_base_path(self) -> Path:
        """Path to base.qss."""
        return self.themes_dir / "base.qss"

    @property
    def theme_vars_path(self) -> Path:
        """Path to variables.json."""
        return self.themes_dir / "variables.json"

    def ensure_directories(self) -> None:
        """Ensure all required directories exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def get_info(self) -> dict:
        """Get path information for debugging."""
        return {
            "project_root": str(self.project_root),
            "data_dir": str(self.data_dir),
            "hot_store": str(self.hot_store_path),
            "cold_store": str(self.cold_store_path),
            "settings": str(self.settings_path),
            "resources": str(self.resources_dir),
        }

    def __repr__(self) -> str:
        return f"PathsConfig(data_dir={self.data_dir})"


PATHS = PathsConfig()
