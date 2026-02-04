# src/iFactory/infrastructure/configuration/db_settings.py
"""
Database Configuration - Production-ready with Pydantic v2.

FEATURES v2.0:
- Environment variable support with prefixes
- Connection URL builders for multiple databases
- Connection pooling configuration
- Health check utilities
- Secure password handling
- Validation and normalization
"""

from __future__ import annotations

import logging
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, Dict, Final, Optional
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
DEFAULT_CONNECT_TIMEOUT: Final[int] = 10
DEFAULT_COMMAND_TIMEOUT: Final[int] = 30


# ============================================================================
# Pool Configuration
# ============================================================================


class PoolConfig:
    """Connection pool configuration."""

    def __init__(
        self,
        pool_size: int = DEFAULT_POOL_SIZE,
        max_overflow: int = DEFAULT_MAX_OVERFLOW,
        pool_timeout: int = DEFAULT_POOL_TIMEOUT,
        pool_recycle: int = DEFAULT_POOL_RECYCLE,
        pool_pre_ping: bool = True,
    ):
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.pool_timeout = pool_timeout
        self.pool_recycle = pool_recycle
        self.pool_pre_ping = pool_pre_ping

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "pool_pre_ping": self.pool_pre_ping,
        }


# ============================================================================
# Database Configuration
# ============================================================================


class DatabaseConfig(BaseSettings):
    """
    Database configuration with environment variable support.

    Environment Variables (prefix: DB_):
        DB_MSSQL_HOST: MSSQL server hostname
        DB_MSSQL_PORT: MSSQL server port (default: 1433)
        DB_MSSQL_DB: Database name
        DB_MSSQL_USER: Username
        DB_MSSQL_PASSWORD: Password (SecretStr)
        DB_MSSQL_DRIVER: ODBC driver name
        DB_MSSQL_TIMEOUT: Query timeout
        DB_MSSQL_CONNECT_TIMEOUT: Connection timeout
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
        env_nested_delimiter="__",
    )

    # ========================================================================
    # MSSQL Settings
    # ========================================================================

    mssql_host: Optional[str] = Field(
        default=None,
        description="MSSQL server hostname or IP",
        json_schema_extra={"env": "DB_MSSQL_HOST"},
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
        default=DEFAULT_COMMAND_TIMEOUT,
        ge=5,
        le=300,
        description="Query timeout in seconds",
    )

    mssql_connect_timeout: int = Field(
        default=DEFAULT_CONNECT_TIMEOUT,
        ge=5,
        le=60,
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
            "17": "ODBC Driver 17 for SQL Server",
            "18": "ODBC Driver 18 for SQL Server",
        }

        return driver_map.get(driver.lower(), driver)

    @model_validator(mode="after")
    def validate_mssql_config(self) -> "DatabaseConfig":
        """Validate MSSQL configuration completeness."""
        has_host = bool(self.mssql_host)
        has_db = bool(self.mssql_db)
        has_user = bool(self.mssql_user)
        has_pass = bool(self.mssql_password)

        # If any MSSQL setting is provided, check completeness
        if any([has_host, has_db]) and not all([has_host, has_db]):
            logger.warning("Incomplete MSSQL configuration. " "Required: mssql_host, mssql_db")

        return self

    # ========================================================================
    # SQLite URLs (Local Storage)
    # ========================================================================

    @cached_property
    def storage_db_path(self) -> Path:
        """Get storage database path."""
        PATHS.storage_dir.mkdir(parents=True, exist_ok=True)
        return PATHS.storage_db_path

    @cached_property
    def storage_db_url(self) -> str:
        """SQLite async URL for local storage database."""
        return f"sqlite+aiosqlite:///{self.storage_db_path}"

    @cached_property
    def storage_db_sync_url(self) -> str:
        """Synchronous SQLite URL for local storage."""
        return f"sqlite:///{self.storage_db_path}"

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
            f"Connection Timeout={self.mssql_connect_timeout}",
            f"Command Timeout={self.mssql_timeout}",
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

    # Alias for backward compatibility
    @property
    def mssql_url(self) -> Optional[str]:
        """Alias for mssql_async_url."""
        return self.mssql_async_url

    # ========================================================================
    # Engine Configuration
    # ========================================================================

    def get_pool_config(self) -> PoolConfig:
        """Get pool configuration object."""
        return PoolConfig(
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
        )

    def get_engine_options(
        self,
        *,
        async_mode: bool = True,
        use_pool: bool = True,
    ) -> Dict[str, Any]:
        """
        Get SQLAlchemy engine options.

        Args:
            async_mode: Whether engine is async
            use_pool: Whether to use connection pooling

        Returns:
            Dictionary of engine options
        """
        options: Dict[str, Any] = {
            "echo": self.echo,
            "pool_pre_ping": True,
        }

        if use_pool:
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

        except ImportError:
            return False, "aioodbc not installed"
        except Exception as e:
            return False, f"Connection failed: {e}"

    def check_sqlite_path(self) -> tuple[bool, str]:
        """
        Check SQLite storage path.

        Returns:
            Tuple of (success, message)
        """
        try:
            storage_path = self.storage_db_path
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

    def get_status(self) -> Dict[str, Any]:
        """Get configuration status summary."""
        return {
            "mssql_configured": self.is_mssql_configured,
            "mssql_host": self.mssql_host,
            "mssql_db": self.mssql_db,
            "mssql_driver": self.mssql_driver,
            "storage_path": str(self.storage_db_path),
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
        }


# ============================================================================
# Module-level convenience functions
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


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "DatabaseConfig",
    "PoolConfig",
    "get_db_config",
    "reset_db_config",
]
