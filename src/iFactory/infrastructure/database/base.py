"""
Database base classes with common functionality.

Provides:
    - Base ORM classes for Hot and Cold stores
    - Timestamp mixin for automatic tracking
    - Common model utilities
"""

from __future__ import annotations
from datetime import datetime
from typing import Any, TypeVar, Type
from sqlalchemy import DateTime, func, inspect
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

__all__ = ["HotBase", "ColdBase", "TimestampMixin", "BaseModel"]
T = TypeVar("T", bound="BaseModel")


class TimestampMixin:
    """
    Mixin for automatic timestamp tracking.

    Adds:
        - created_at: Set on insert
        - updated_at: Updated on each change
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime, onupdate=func.now(), nullable=True
    )


class BaseModel(DeclarativeBase):
    """
    Enhanced base class with common utilities.

    All ORM models inherit from this class (via HotBase or ColdBase).
    Provides serialization and factory methods.
    """

    __abstract__ = True

    def to_dict(self) -> dict[str, Any]:
        """
        Convert model to dictionary.

        Returns:
            Dictionary with all column values
        """
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}

    @classmethod
    def from_dict(cls: Type[T], data: dict[str, Any]) -> T:
        """
        Create instance from dictionary.

        Args:
            data: Dictionary with column values

        Returns:
            New model instance
        """
        columns = {c.name for c in cls.__table__.columns}
        filtered = {k: v for (k, v) in data.items() if k in columns}
        return cls(**filtered)

    @classmethod
    def get_columns(cls) -> list[str]:
        """Get list of column names."""
        return [c.name for c in cls.__table__.columns]

    @classmethod
    def get_primary_key_columns(cls) -> list[str]:
        """Get primary key column names."""
        return [c.name for c in cls.__table__.primary_key.columns]

    def get_primary_key_values(self) -> dict[str, Any]:
        """Get primary key values."""
        pk_cols = self.get_primary_key_columns()
        return {col: getattr(self, col) for col in pk_cols}

    def update_from_dict(self, data: dict[str, Any]) -> None:
        """
        Update model from dictionary.

        Args:
            data: Dictionary with new values
        """
        columns = {c.name for c in self.__table__.columns}
        for key, value in data.items():
            if key in columns and hasattr(self, key):
                setattr(self, key, value)

    def __repr__(self) -> str:
        """Detailed representation for debugging."""
        pk_cols = self.get_primary_key_columns()
        pk_vals = ", ".join((f"{c}={getattr(self, c)!r}" for c in pk_cols))
        return f"<{self.__class__.__name__}({pk_vals})>"

    def __eq__(self, other: object) -> bool:
        """Compare by primary key."""
        if not isinstance(other, self.__class__):
            return False
        return self.get_primary_key_values() == other.get_primary_key_values()

    def __hash__(self) -> int:
        """Hash by primary key."""
        pk_values = tuple(self.get_primary_key_values().values())
        return hash((self.__class__.__name__, pk_values))


class HotBase(BaseModel):
    """
    Base for hot (frequently updated) data.

    Hot store contains latest state data that changes frequently:
        - Latest device status
        - Latest material input
        - Sync metadata
    """

    __abstract__ = True


class ColdBase(BaseModel):
    """
    Base for cold (historical) data.

    Cold store contains historical records for reporting:
        - Status history
        - Input history
    """

    __abstract__ = True
