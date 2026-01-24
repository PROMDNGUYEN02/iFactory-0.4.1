"""
Unit of Work interface - Transaction management pattern.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from types import TracebackType
from typing import Optional, Type

from iFactory.domain.repositories import (
    DeviceRepository,
    InputRepository,
    StatusRepository,
    SyncMetadataRepository,
)

__all__ = ["UnitOfWork"]


class UnitOfWork(ABC):
    """
    Abstract Unit of Work for transaction management.
    """

    @property
    @abstractmethod
    def devices(self) -> DeviceRepository:
        """Repository for accessing Device entities."""
        pass

    @property
    @abstractmethod
    def statuses(self) -> StatusRepository:
        """Repository for accessing DeviceStateHistory entities."""
        pass

    @property
    @abstractmethod
    def inputs(self) -> InputRepository:
        """Repository for accessing Input data entities."""
        pass

    @property
    @abstractmethod
    def sync_metadata(self) -> SyncMetadataRepository:
        """Repository for accessing synchronization metadata."""
        pass

    @abstractmethod
    async def begin(self) -> None:
        """Begin a new transaction."""
        pass

    @abstractmethod
    async def commit(self) -> None:
        """Commit the current transaction, persisting changes."""
        pass

    @abstractmethod
    async def rollback(self) -> None:
        """Rollback the current transaction, discarding changes."""
        pass

    async def __aenter__(self) -> "UnitOfWork":
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        if exc_type is not None:
            await self.rollback()
        else:
            try:
                await self.commit()
            except Exception:
                await self.rollback()
                raise
