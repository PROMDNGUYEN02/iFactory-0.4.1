"""
Infrastructure: Application Paths Management.
Ensures system directories (data, logs, db) exist.
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

        # 1. Định nghĩa các thư mục chính
        self.data_dir = self.project_root / "data"
        self.config_dir = self.data_dir / "config"
        self.storage_dir = self.data_dir / "storage"
        self.logs_dir = self.project_root / "logs"

        # 2. Cập nhật đường dẫn Database (trỏ vào storage)
        self.hot_db_path = self.storage_dir / "hot_store.db"
        self.cold_db_path = self.storage_dir / "cold_store.db"

        # 3. Cập nhật đường dẫn Config (trỏ vào config)
        self.settings_path = self.config_dir / "settings.json"
        self.device_positions_path = self.config_dir / "device_positions.json"
        self.legends_path = self.config_dir / "legends.json"

    def ensure_directories(self) -> None:
        """
        Creates necessary directories if they do not exist.
        """
        # Thêm self.config_dir vào danh sách tạo thư mục
        for directory in [self.data_dir, self.config_dir, self.storage_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)


# Global instance for easy access, but prefer DI where possible.
PATHS = AppPaths()
