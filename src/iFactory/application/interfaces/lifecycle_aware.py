"""
Lifecycle Aware Interface.

Interface for components that need initialization and cleanup.
Used by infrastructure implementations that have lifecycle concerns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

__all__ = ["LifecycleAware"]


class LifecycleAware(ABC):
    """
    Interface for components with lifecycle requirements.

    Infrastructure implementations (repositories, caches, data sources)
    may implement this for proper resource management.
    """

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the component.

        Called during application startup.
        Should create tables, connections, caches, etc.
        """
        pass

    @abstractmethod
    async def dispose(self) -> None:
        """
        Clean up resources.

        Called during application shutdown.
        Should close connections, clear caches, etc.
        """
        pass

    async def __aenter__(self):
        """Support async context manager."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Support async context manager with automatic cleanup."""
        await self.dispose()
