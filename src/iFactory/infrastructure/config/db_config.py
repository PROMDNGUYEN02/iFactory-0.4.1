from dataclasses import dataclass

from .app_paths import AppPaths


@dataclass
class DatabaseConfig:
    """Configuration for database connections."""

    connection_string: str
    pool_size: int = 5
    max_overflow: int = 10
    echo: bool = False

    @classmethod
    def default_sqlite(cls) -> "DatabaseConfig":
        db_path = AppPaths.get_data_path() / "ifactory.db"
        return cls(
            connection_string=f"sqlite+aiosqlite:///{db_path}",
            echo=False,
        )
