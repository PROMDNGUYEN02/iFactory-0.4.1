"""
Database configuration - Immutable configuration objects.
"""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Optional

__all__ = ["DatabaseType", "DBConfig", "RemoteDBParams", "HealthStatus"]


class DatabaseType(Enum):
    """Database type enumeration."""

    SQLITE_HOT = auto()
    SQLITE_COLD = auto()
    MSSQL = auto()


@dataclass(frozen=True, slots=True)
class DBConfig:
    """
    Immutable database configuration.

    Attributes:
        echo: Enable SQL logging
        cache_size: SQLite cache size (negative = KB)
        mmap_size: SQLite memory-mapped I/O size
        pool_size: Connection pool size
        max_overflow: Max connections above pool_size
        pool_timeout: Timeout waiting for connection
        pool_recycle: Recycle connections after N seconds
        connect_timeout: Connection establishment timeout
        command_timeout: Command execution timeout
    """

    echo: bool = False
    cache_size: int = 100000
    mmap_size: int = 30000000000
    pool_size: int = 20
    max_overflow: int = 40
    pool_timeout: int = 30
    pool_recycle: int = 1800
    connect_timeout: int = 30
    command_timeout: int = 60
    wal_autocheckpoint: int = 1000
    busy_timeout: int = 5000

    @classmethod
    def development(cls) -> "DBConfig":
        """Create development configuration."""
        return cls(echo=True, pool_size=5, max_overflow=10)

    @classmethod
    def production(cls) -> "DBConfig":
        """Create production configuration."""
        return cls(echo=False, pool_size=20, max_overflow=40)

    @classmethod
    def testing(cls) -> "DBConfig":
        """Create testing configuration."""
        return cls(echo=False, pool_size=1, max_overflow=0)


@dataclass(slots=True)
class RemoteDBParams:
    """
    Remote database connection parameters.

    Can be configured via:
        - Direct DSN string
        - Individual connection components
        - Environment variables
    """

    dsn: str = ""
    host: str = ""
    database: str = ""
    user: str = ""
    password: str = field(default="", repr=False)
    driver: str = ""
    port: int = 1433
    encrypt: bool = False
    trust_cert: bool = True

    @classmethod
    def from_env(cls, prefix: str = "MSSQL_") -> "RemoteDBParams":
        """
        Create from environment variables.

        Looks for:
            - {prefix}HOST
            - {prefix}DATABASE
            - {prefix}USER
            - {prefix}PASSWORD
            - {prefix}DRIVER
            - {prefix}PORT
            - {prefix}DSN (if set, used directly)
        """
        return cls(
            dsn=os.getenv(f"{prefix}DSN", ""),
            host=os.getenv(f"{prefix}HOST", ""),
            database=os.getenv(f"{prefix}DATABASE", ""),
            user=os.getenv(f"{prefix}USER", ""),
            password=os.getenv(f"{prefix}PASSWORD", ""),
            driver=os.getenv(f"{prefix}DRIVER", ""),
            port=int(os.getenv(f"{prefix}PORT", "1433")),
        )

    @property
    def is_configured(self) -> bool:
        """Check if minimum connection info is provided."""
        return bool(self.dsn or (self.host and self.database))

    def validate(self) -> list[str]:
        """Validate configuration and return list of errors."""
        errors = []
        if not self.dsn:
            if not self.host:
                errors.append("Host is required")
            if not self.database:
                errors.append("Database is required")
        return errors

    def to_dict(self) -> dict[str, str]:
        """Convert to dictionary (excludes password)."""
        return {
            "host": self.host,
            "database": self.database,
            "user": self.user,
            "driver": self.driver,
            "port": str(self.port),
            "has_dsn": bool(self.dsn),
            "has_password": bool(self.password),
        }


@dataclass(slots=True)
class HealthStatus:
    """
    Database health check result.

    Attributes:
        name: Database identifier
        healthy: True if healthy
        latency_ms: Response time in milliseconds
        error: Error message if unhealthy
        details: Additional status details
    """

    name: str
    healthy: bool
    latency_ms: float = 0.0
    error: str = ""
    details: dict = field(default_factory=dict)

    def __bool__(self) -> bool:
        """Allow boolean evaluation."""
        return self.healthy

    @classmethod
    def success(cls, name: str, latency_ms: float, **details) -> "HealthStatus":
        """Create successful health status."""
        return cls(name=name, healthy=True, latency_ms=latency_ms, details=details)

    @classmethod
    def failure(cls, name: str, error: str, **details) -> "HealthStatus":
        """Create failed health status."""
        return cls(name=name, healthy=False, error=error, details=details)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        result = {
            "name": self.name,
            "healthy": self.healthy,
            "latency_ms": round(self.latency_ms, 2),
        }
        if self.error:
            result["error"] = self.error
        if self.details:
            result["details"] = self.details
        return result
