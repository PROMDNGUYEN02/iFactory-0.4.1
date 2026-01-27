import sys
from pathlib import Path


class AppPaths:
    """
    Centralized path management for the application.
    Resolves paths relative to the executable or source root.
    """

    @staticmethod
    def get_base_path() -> Path:
        if getattr(sys, "frozen", False):
            return Path(sys.executable).parent
        return Path(__file__).parent.parent.parent.parent.parent

    @staticmethod
    def get_config_path() -> Path:
        return AppPaths.get_base_path() / "config"

    @staticmethod
    def get_logs_path() -> Path:
        logs = AppPaths.get_base_path() / "logs"
        logs.mkdir(exist_ok=True)
        return logs

    @staticmethod
    def get_data_path() -> Path:
        data = AppPaths.get_base_path() / "data"
        data.mkdir(exist_ok=True)
        return data
