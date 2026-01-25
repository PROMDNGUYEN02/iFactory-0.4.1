from dataclasses import dataclass
import os


@dataclass(frozen=True)
class DatabaseConfig:
    connection_string: str
    echo: bool
    pool_size: int
    max_overflow: int


def load_database_config() -> DatabaseConfig:
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///ifactory.db")
    return DatabaseConfig(
        connection_string=db_url,
        echo=os.getenv("DB_ECHO", "false").lower() == "true",
        pool_size=int(os.getenv("DB_POOL_SIZE", "5")),
        max_overflow=int(os.getenv("DB_MAX_OVERFLOW", "10")),
    )
