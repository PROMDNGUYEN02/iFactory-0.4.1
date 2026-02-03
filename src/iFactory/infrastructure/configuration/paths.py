# src/iFactory/infrastructure/configuration/paths.py
"""
Infrastructure: Application Paths Management.
Supports both development and PyInstaller frozen environments.
"""

import sys
import shutil
from functools import lru_cache
from pathlib import Path


def is_frozen() -> bool:
    """Check if running from PyInstaller bundle."""
    return getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS")


def _find_project_root_dev() -> Path:
    """
    Find project root in development mode.

    paths.py location: src/iFactory/infrastructure/configuration/paths.py
    Project root is 4 levels up from this file.
    """
    # Cách 1: Đi lên 4 cấp từ file này
    this_file = Path(__file__).resolve()
    # src/iFactory/infrastructure/configuration/paths.py
    #  4      3          2             1           0
    candidate = this_file.parents[4]

    # Verify đây là project root
    if (candidate / "src").is_dir() or (candidate / "pyproject.toml").is_file():
        return candidate

    # Cách 2: Tìm ngược lên từ cwd
    cwd = Path.cwd()
    for parent in [cwd] + list(cwd.parents):
        if (parent / "src").is_dir() and (parent / "data").is_dir():
            return parent
        if (parent / "pyproject.toml").is_file():
            return parent

    # Cách 3: Fallback về cwd
    return cwd


@lru_cache(maxsize=1)
def get_bundle_dir() -> Path:
    """
    Bundle directory (where bundled resources are).
    - PyInstaller: sys._MEIPASS (temp extraction folder)
    - Development: project root
    """
    if is_frozen():
        return Path(sys._MEIPASS)
    return _find_project_root_dev()


@lru_cache(maxsize=1)
def get_app_dir() -> Path:
    """
    Application directory (for writable files).
    - PyInstaller: folder containing .exe
    - Development: project root
    """
    if is_frozen():
        return Path(sys.executable).parent
    return _find_project_root_dev()


# Legacy alias
@lru_cache(maxsize=1)
def get_project_root() -> Path:
    return get_app_dir()


class AppPaths:
    """
    Application paths manager.
    Automatically handles development vs frozen (PyInstaller) modes.
    """

    def __init__(self) -> None:
        self._frozen = is_frozen()
        self._bundle_dir = get_bundle_dir()
        self._app_dir = get_app_dir()

        # === Writable paths (data, logs) ===
        self.data_dir = self._app_dir / "data"
        self.config_dir = self.data_dir / "config"
        self.storage_dir = self.data_dir / "storage"
        self.logs_dir = self._app_dir / "logs"

        # Database
        self.storage_db_path = self.storage_dir / "storage.db"
        self.hot_db_path = self.storage_db_path  # Legacy
        self.cold_db_path = self.storage_db_path  # Legacy

        # Config files
        self.settings_path = self.config_dir / "settings.json"
        self.device_positions_path = self.config_dir / "device_positions.json"
        self.legends_path = self.config_dir / "legends.json"

        # Legacy
        self.project_root = self._app_dir

    @property
    def src_dir(self) -> Path:
        """Source directory."""
        if self._frozen:
            return self._bundle_dir
        return self._app_dir / "src"

    @property
    def resources_dir(self) -> Path:
        """Resources directory (icons, themes, qss)."""
        if self._frozen:
            # PyInstaller: bundled at iFactory/presentation/resources
            return self._bundle_dir / "iFactory" / "presentation" / "resources"
        # Dev: src/iFactory/presentation/resources
        return self.src_dir / "iFactory" / "presentation" / "resources"

    @property
    def themes_dir(self) -> Path:
        return self.resources_dir / "themes"

    @property
    def icons_dir(self) -> Path:
        return self.resources_dir / "icon"

    @property
    def env_file(self) -> Path:
        """Get .env file path."""
        # Check app dir first (user can override)
        app_env = self._app_dir / ".env"
        if app_env.exists():
            return app_env
        # Then bundle
        bundle_env = self._bundle_dir / ".env"
        if bundle_env.exists():
            return bundle_env
        return app_env

    def ensure_directories(self) -> None:
        """Create necessary directories."""
        for d in [self.data_dir, self.config_dir, self.storage_dir, self.logs_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def initialize_config_files(self) -> None:
        """Copy bundled configs to writable location (frozen mode only)."""
        if not self._frozen:
            return

        self.ensure_directories()

        bundle_config = self._bundle_dir / "data" / "config"
        for filename in ["settings.json", "device_positions.json"]:
            dest = self.config_dir / filename
            src = bundle_config / filename
            if not dest.exists() and src.exists():
                shutil.copy2(src, dest)

    def get_resource_path(self, relative_path: str) -> Path:
        """Get absolute path to a resource."""
        return self.resources_dir / relative_path

    def __repr__(self) -> str:
        return f"AppPaths(frozen={self._frozen}, " f"app_dir='{self._app_dir}', " f"resources='{self.resources_dir}')"


# === Global singleton ===
PATHS = AppPaths()
