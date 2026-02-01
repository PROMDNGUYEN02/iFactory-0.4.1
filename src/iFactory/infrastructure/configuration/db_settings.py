"""
Infrastructure: Database Configuration.
Simplified: Single storage database.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from iFactory.infrastructure.configuration.paths import PATHS


class DatabaseConfig(BaseSettings):
    """
    Database configuration settings.
    Prioritizes environment variables (prefix DB_).
    """

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite storage
    storage_db_url: str = Field(default=f"sqlite:///{PATHS.storage_db_path}")

    # Legacy compatibility
    @property
    def hot_db_url(self) -> str:
        return self.storage_db_url

    @property
    def cold_db_url(self) -> str:
        return self.storage_db_url

    # MSSQL (Remote)
    mssql_host: str | None = None
    mssql_db: str | None = None
    mssql_user: str | None = None
    mssql_password: str | None = None
    mssql_driver: str = "ODBC Driver 17 for SQL Server"

    pool_size: int = 20
    max_overflow: int = 40
    echo: bool = False

    @property
    def mssql_url(self) -> str | None:
        if not (self.mssql_host and self.mssql_db):
            return None
        driver = self.mssql_driver.replace(" ", "+")
        return f"mssql+aioodbc://{self.mssql_user}:{self.mssql_password}@" f"{self.mssql_host}/{self.mssql_db}?driver={driver}"
