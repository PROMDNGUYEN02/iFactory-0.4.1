"""
Infrastructure: Async SQLAlchemy Engine Configuration.

Sử dụng driver `aiosqlite` để không làm treo giao diện PyQt/PySide6.
"""

from functools import lru_cache
from typing import Optional

from sqlalchemy.ext.asyncio import create_async_engine, AsyncEngine
from iFactory.infrastructure.config.db_config import DatabaseConfig


@lru_cache(maxsize=1)
def get_hot_engine() -> AsyncEngine:
    """Khởi tạo Async Engine cho Hot Storage."""
    config = DatabaseConfig()
    # Chuyển sqlite:/// thành sqlite+aiosqlite:///
    url = config.hot_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(url, echo=config.echo)


@lru_cache(maxsize=1)
def get_cold_engine() -> AsyncEngine:
    """Khởi tạo Async Engine cho Cold Storage."""
    config = DatabaseConfig()
    url = config.cold_db_url.replace("sqlite:///", "sqlite+aiosqlite:///")
    return create_async_engine(url, echo=config.echo)


@lru_cache(maxsize=1)
def get_mssql_engine() -> Optional[AsyncEngine]:
    """Khởi tạo Async Engine cho MSSQL (sử dụng aioodbc)."""
    config = DatabaseConfig()
    url = config.mssql_url

    if not url:
        return None

    # Chuyển pyodbc sang aioodbc cho async
    async_url = url.replace("pyodbc", "aioodbc")
    return create_async_engine(
        async_url,
        echo=config.echo,
        pool_size=config.pool_size,
        max_overflow=config.max_overflow,
        pool_timeout=30,
        pool_recycle=180,
    )
