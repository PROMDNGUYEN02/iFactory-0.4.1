"""
Infrastructure: Application Paths Management.
Simplified: Single storage database.
"""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Returns the project root directory."""
    return Path(__file__).resolve().parents[4]


class AppPaths:
    def __init__(self) -> None:
        self.project_root = get_project_root()

        # Main directories
        self.data_dir = self.project_root / "data"
        self.config_dir = self.data_dir / "config"
        self.storage_dir = self.data_dir / "storage"
        self.logs_dir = self.project_root / "logs"

        # Storage database
        self.storage_db_path = self.storage_dir / "storage.db"

        # Legacy compatibility
        self.hot_db_path = self.storage_db_path
        self.cold_db_path = self.storage_db_path

        # Config files
        self.settings_path = self.config_dir / "settings.json"
        self.device_positions_path = self.config_dir / "device_positions.json"
        self.legends_path = self.config_dir / "legends.json"

    def ensure_directories(self) -> None:
        """Creates necessary directories if they do not exist."""
        for directory in [self.data_dir, self.config_dir, self.storage_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)


# Global instance
PATHS = AppPaths()
