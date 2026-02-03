# src/iFactory/infrastructure/configuration/db_settings.py
"""
Infrastructure: Database Configuration - Enhanced with Pydantic v2.

Features:
- Pydantic Settings with env variable support
- Connection URL builders for multiple databases
- Connection pooling configuration
- Health check utilities
"""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, Final, Optional
from urllib.parse import quote_plus

from pydantic import (
    Field,
    SecretStr,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict

from iFactory.infrastructure.configuration.paths import PATHS

logger = logging.getLogger(__name__)


# ============================================================================
# Constants
# ============================================================================

DEFAULT_POOL_SIZE: Final[int] = 20
DEFAULT_MAX_OVERFLOW: Final[int] = 40
DEFAULT_POOL_TIMEOUT: Final[int] = 30
DEFAULT_POOL_RECYCLE: Final[int] = 1800  # 30 minutes


# ============================================================================
# Database Configuration
# ============================================================================


class DatabaseConfig(BaseSettings):
    """
    Database configuration with environment variable support.

    Environment Variables (prefix: DB_):
        DB_MSSQL_HOST: MSSQL server hostname
        DB_MSSQL_DB: Database name
        DB_MSSQL_USER: Username
        DB_MSSQL_PASSWORD: Password (SecretStr)
        DB_MSSQL_DRIVER: ODBC driver name
        DB_POOL_SIZE: Connection pool size
        DB_MAX_OVERFLOW: Max pool overflow
        DB_ECHO: Enable SQL echo logging

    Usage:
        config = DatabaseConfig()

        # SQLite for local storage
        sqlite_url = config.storage_db_url

        # MSSQL for remote data
        if config.is_mssql_configured:
            mssql_url = config.mssql_async_url
    """

    model_config = SettingsConfigDict(
        env_prefix="DB_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        # Pydantic v2: Use env_nested_delimiter for nested settings
        env_nested_delimiter="__",
    )

    # ========================================================================
    # MSSQL Settings
    # ========================================================================

    mssql_host: Optional[str] = Field(
        default=None,
        description="MSSQL server hostname or IP",
    )

    mssql_port: int = Field(
        default=1433,
        ge=1,
        le=65535,
        description="MSSQL server port",
    )

    mssql_db: Optional[str] = Field(
        default=None,
        description="MSSQL database name",
    )

    mssql_user: Optional[str] = Field(
        default=None,
        description="MSSQL username",
    )

    mssql_password: Optional[SecretStr] = Field(
        default=None,
        description="MSSQL password",
    )

    mssql_driver: str = Field(
        default="ODBC Driver 17 for SQL Server",
        description="ODBC driver name",
    )

    mssql_trust_cert: bool = Field(
        default=True,
        description="Trust server certificate",
    )

    mssql_timeout: int = Field(
        default=30,
        ge=5,
        le=300,
        description="Connection timeout in seconds",
    )

    # ========================================================================
    # Pool Settings
    # ========================================================================

    pool_size: int = Field(
        default=DEFAULT_POOL_SIZE,
        ge=1,
        le=100,
        description="Connection pool size",
    )

    max_overflow: int = Field(
        default=DEFAULT_MAX_OVERFLOW,
        ge=0,
        le=200,
        description="Max connections beyond pool_size",
    )

    pool_timeout: int = Field(
        default=DEFAULT_POOL_TIMEOUT,
        ge=5,
        le=300,
        description="Pool connection timeout",
    )

    pool_recycle: int = Field(
        default=DEFAULT_POOL_RECYCLE,
        ge=60,
        le=7200,
        description="Connection recycle time in seconds",
    )

    echo: bool = Field(
        default=False,
        description="Echo SQL statements",
    )

    # ========================================================================
    # Validators
    # ========================================================================

    @field_validator("mssql_driver", mode="before")
    @classmethod
    def normalize_driver(cls, v: Any) -> str:
        """Normalize ODBC driver name."""
        if not v:
            return "ODBC Driver 17 for SQL Server"

        driver = str(v).strip()

        # Handle common variations
        driver_map = {
            "sql server": "SQL Server",
            "odbc driver 17": "ODBC Driver 17 for SQL Server",
            "odbc driver 18": "ODBC Driver 18 for SQL Server",
        }

        return driver_map.get(driver.lower(), driver)

    @model_validator(mode="after")
    def validate_mssql_config(self) -> "DatabaseConfig":
        """Validate MSSQL configuration completeness."""
        has_host = bool(self.mssql_host)
        has_db = bool(self.mssql_db)
        has_user = bool(self.mssql_user)
        has_pass = bool(self.mssql_password)

        # If any MSSQL setting is provided, all required ones must be present
        if any([has_host, has_db]) and not all([has_host, has_db, has_user]):
            logger.warning("Incomplete MSSQL configuration. " "Required: mssql_host, mssql_db, mssql_user")

        return self

    # ========================================================================
    # SQLite URLs (Local Storage)
    # ========================================================================

    @cached_property
    def storage_db_url(self) -> str:
        """SQLite URL for local storage database."""
        PATHS.storage_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite+aiosqlite:///{PATHS.storage_db_path}"

    @cached_property
    def storage_db_sync_url(self) -> str:
        """Synchronous SQLite URL for local storage."""
        PATHS.storage_dir.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{PATHS.storage_db_path}"

    # Aliases for backward compatibility
    @property
    def hot_db_url(self) -> str:
        return self.storage_db_url

    @property
    def cold_db_url(self) -> str:
        return self.storage_db_url

    # ========================================================================
    # MSSQL URLs
    # ========================================================================

    @property
    def is_mssql_configured(self) -> bool:
        """Check if MSSQL is properly configured."""
        return bool(self.mssql_host and self.mssql_db and self.mssql_user and self.mssql_password)

    @cached_property
    def mssql_connection_string(self) -> Optional[str]:
        """
        ODBC connection string for pyodbc/aioodbc.

        Returns None if MSSQL is not configured.
        """
        if not self.is_mssql_configured:
            return None

        password = self.mssql_password.get_secret_value() if self.mssql_password else ""

        parts = [
            f"DRIVER={{{self.mssql_driver}}}",
            f"SERVER={self.mssql_host},{self.mssql_port}",
            f"DATABASE={self.mssql_db}",
            f"UID={self.mssql_user}",
            f"PWD={password}",
            f"Connection Timeout={self.mssql_timeout}",
        ]

        if self.mssql_trust_cert:
            parts.append("TrustServerCertificate=yes")

        return ";".join(parts)

    @cached_property
    def mssql_async_url(self) -> Optional[str]:
        """
        SQLAlchemy async URL for MSSQL (aioodbc).

        Returns None if MSSQL is not configured.
        """
        conn_str = self.mssql_connection_string
        if not conn_str:
            return None

        encoded = quote_plus(conn_str)
        return f"mssql+aioodbc:///?odbc_connect={encoded}"

    @cached_property
    def mssql_sync_url(self) -> Optional[str]:
        """
        SQLAlchemy sync URL for MSSQL (pyodbc).

        Returns None if MSSQL is not configured.
        """
        conn_str = self.mssql_connection_string
        if not conn_str:
            return None

        encoded = quote_plus(conn_str)
        return f"mssql+pyodbc:///?odbc_connect={encoded}"

    # Aliases for backward compatibility
    @property
    def mssql_url(self) -> Optional[str]:
        """Alias for mssql_async_url."""
        return self.mssql_async_url

    # ========================================================================
    # Engine Configuration
    # ========================================================================

    def get_engine_options(self, *, async_mode: bool = True) -> dict[str, Any]:
        """
        Get SQLAlchemy engine options.

        Args:
            async_mode: Whether engine is async

        Returns:
            Dictionary of engine options
        """
        options: dict[str, Any] = {
            "echo": self.echo,
            "pool_pre_ping": True,  # Verify connections before use
        }

        # Pool settings (not applicable to SQLite in async mode)
        if not async_mode or "mssql" in str(self.mssql_async_url or ""):
            options.update(
                {
                    "pool_size": self.pool_size,
                    "max_overflow": self.max_overflow,
                    "pool_timeout": self.pool_timeout,
                    "pool_recycle": self.pool_recycle,
                }
            )

        return options

    # ========================================================================
    # Health Check
    # ========================================================================

    async def check_mssql_connection(self) -> tuple[bool, str]:
        """
        Test MSSQL connection.

        Returns:
            Tuple of (success, message)
        """
        if not self.is_mssql_configured:
            return False, "MSSQL not configured"

        try:
            import aioodbc

            async with aioodbc.connect(
                dsn=self.mssql_connection_string,
                timeout=5,
            ) as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute("SELECT 1")
                    await cursor.fetchone()

            return True, "Connection successful"

        except Exception as e:
            return False, f"Connection failed: {e}"

    def check_sqlite_path(self) -> tuple[bool, str]:
        """
        Check SQLite storage path.

        Returns:
            Tuple of (success, message)
        """
        try:
            storage_path = PATHS.storage_db_path
            storage_dir = storage_path.parent

            if not storage_dir.exists():
                storage_dir.mkdir(parents=True, exist_ok=True)

            # Check write permission
            test_file = storage_dir / ".write_test"
            test_file.touch()
            test_file.unlink()

            return True, f"Storage path OK: {storage_path}"

        except Exception as e:
            return False, f"Storage path error: {e}"


# ============================================================================
# Module-level convenience function
# ============================================================================

_db_config: Optional[DatabaseConfig] = None


def get_db_config() -> DatabaseConfig:
    """Get the database configuration singleton."""
    global _db_config
    if _db_config is None:
        _db_config = DatabaseConfig()
    return _db_config


def reset_db_config() -> None:
    """Reset the database configuration (for testing)."""
    global _db_config
    _db_config = None


__all__ = [
    "DatabaseConfig",
    "get_db_config",
    "reset_db_config",
]
