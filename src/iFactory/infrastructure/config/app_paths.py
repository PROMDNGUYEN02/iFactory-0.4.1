"""
Infrastructure: Application Paths Management.
Đảm bảo các thư mục hệ thống (data, logs, db) luôn tồn tại.
"""

from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=1)
def get_project_root() -> Path:
    """Trả về thư mục gốc của project."""
    return Path(__file__).resolve().parents[4]


class AppPaths:
    def __init__(self):
        self.project_root = get_project_root()
        self.data_dir = self.project_root / "data"
        self.storage_dir = self.data_dir / "storage_data"
        self.logs_dir = self.project_root / "logs"

        # Database paths
        self.hot_db_path = self.data_dir / "hot_store.db"
        self.cold_db_path = self.data_dir / "cold_store.db"

        # Config paths
        self.settings_path = self.data_dir / "settings.json"
        self.device_positions_path = self.data_dir / "device_positions.json"

    def ensure_directories(self) -> None:
        """
        [FIX BUGS] Đảm bảo thư mục tồn tại trước khi SQLAlchemy ghi file.
        """
        for directory in [self.data_dir, self.storage_dir, self.logs_dir]:
            directory.mkdir(parents=True, exist_ok=True)


PATHS = AppPaths()
