# src/iFactory/infrastructure/configuration/db_settings.py
"""
Infrastructure: Database Configuration.
Simplified: Single storage database.
Supports PyInstaller frozen environments.
"""

from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from iFactory.infrastructure.configuration.paths import PATHS


def _get_env_file() -> Optional[str]:
    """Get .env file path if exists."""
    env_path = PATHS.env_file
    if env_path.exists():
        return str(env_path)
    return None


class DatabaseConfig(BaseSettings):
    """
    Database configuration settings.
    Prioritizes environment variables (prefix DB_).
    """

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        case_sensitive=False,
        env_file=_get_env_file(),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # SQLite storage (computed after init)
    @property
    def storage_db_url(self) -> str:
        """SQLite storage URL."""
        # Ensure directory exists
        PATHS.storage_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{PATHS.storage_db_path}"

    @property
    def hot_db_url(self) -> str:
        return self.storage_db_url

    @property
    def cold_db_url(self) -> str:
        return self.storage_db_url

    # MSSQL (Remote) - from .env
    mssql_host: Optional[str] = Field(default=None)
    mssql_db: Optional[str] = Field(default=None)
    mssql_user: Optional[str] = Field(default=None)
    mssql_password: Optional[str] = Field(default=None)
    mssql_driver: str = Field(default="SQL Server")

    # Pool settings
    pool_size: int = 20
    max_overflow: int = 40
    echo: bool = False

    @property
    def mssql_connection_string(self) -> Optional[str]:
        """
        ODBC connection string for pyodbc/aioodbc.
        Returns None if not configured.
        """
        if not self.mssql_host or not self.mssql_db:
            return None

        return (
            f"DRIVER={{{self.mssql_driver}}};"
            f"SERVER={self.mssql_host};"
            f"DATABASE={self.mssql_db};"
            f"UID={self.mssql_user};"
            f"PWD={self.mssql_password};"
            f"TrustServerCertificate=yes;"
        )

    @property
    def mssql_url(self) -> Optional[str]:
        """
        SQLAlchemy URL for aioodbc async driver.
        Returns None if not configured.
        """
        conn_str = self.mssql_connection_string
        if not conn_str:
            return None

        # URL encode the connection string
        encoded = quote_plus(conn_str)
        return f"mssql+aioodbc:///?odbc_connect={encoded}"

    @property
    def mssql_sync_url(self) -> Optional[str]:
        """
        SQLAlchemy URL for pyodbc sync driver.
        Returns None if not configured.
        """
        conn_str = self.mssql_connection_string
        if not conn_str:
            return None

        encoded = quote_plus(conn_str)
        return f"mssql+pyodbc:///?odbc_connect={encoded}"

    def is_mssql_configured(self) -> bool:
        """Check if MSSQL is properly configured."""
        return bool(self.mssql_host and self.mssql_db and self.mssql_user)
