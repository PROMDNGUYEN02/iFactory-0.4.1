"""
Abstract database engine interface.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Generic, TypeVar
from ..config import HealthStatus, DBConfig

__all__ = ["DatabaseEngine", "EngineConfig"]
SessionT = TypeVar("SessionT")


@dataclass
class EngineConfig:
    """Engine-specific configuration."""

    name: str
    echo: bool = False
    pool_size: int = 5
    connect_timeout: int = 30


class DatabaseEngine(ABC, Generic[SessionT]):
    """
    Abstract database engine interface.

    Defines contract for all database engines (SQLite, MSSQL, etc.).
    Generic over session type since SQLite uses AsyncSession
    and MSSQL uses sync Session.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Engine name for logging."""
        pass

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Check if connected."""
        pass

    @abstractmethod
    async def connect(self) -> None:
        """
        Establish connection.

        Should be idempotent - safe to call multiple times.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Close connection and cleanup resources.
        """
        pass

    @abstractmethod
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[SessionT, None]:
        """
        Get database session.

        Yields:
            Session for database operations

        Example:
            async with engine.session() as session:
                result = await session.execute(query)
        """
        yield

    @abstractmethod
    async def health_check(self, timeout: float = 5.0) -> HealthStatus:
        """
        Perform health check.

        Args:
            timeout: Maximum time to wait

        Returns:
            Health status with latency
        """
        pass

    @abstractmethod
    async def get_stats(self) -> dict[str, Any]:
        """
        Get engine statistics.

        Returns:
            Dictionary with engine stats
        """
        pass

    async def __aenter__(self) -> "DatabaseEngine[SessionT]":
        """Async context manager entry."""
        await self.connect()
        return self

    async def __aexit__(self, *_) -> None:
        """Async context manager exit."""
        await self.disconnect()
