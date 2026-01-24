"""
Presentation Container - DI container for presentation layer.

Manages presentation layer dependencies.
"""

from __future__ import annotations
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional
from iFactory.presentation.adapters import AsyncExecutor, QtSignalAdapter
from iFactory.presentation.managers import ThemeManager, IconManager

logger = logging.getLogger(__name__)


@dataclass
class PresentationContainer:
    """
    Dependency container for presentation layer.

    Manages:
        - Theme manager
        - Icon manager
        - Signal adapter
        - Async executor

    Example:
        container = PresentationContainer.create(
            theme_base=Path("themes/base.qss"),
            theme_vars=Path("themes/variables.json"),
        )

        theme = container.theme_manager
        icons = container.icon_manager
    """

    theme_manager: Optional[ThemeManager] = None
    icon_manager: Optional[IconManager] = None
    signal_adapter: Optional[QtSignalAdapter] = None
    async_executor: Optional[AsyncExecutor] = None
    _initialized: bool = field(default=False, repr=False)

    @classmethod
    def create(cls, theme_base: Path, theme_vars: Path, icon_cache_size: int = 100) -> "PresentationContainer":
        """
        Create container with managers.

        Args:
            theme_base: Path to base.qss
            theme_vars: Path to variables.json
            icon_cache_size: Icon cache size

        Returns:
            Initialized container
        """
        container = cls()
        try:
            container.theme_manager = ThemeManager(theme_base, theme_vars)
            container.icon_manager = IconManager(theme_vars, icon_cache_size)
            container.signal_adapter = QtSignalAdapter()
            container.async_executor = AsyncExecutor()
            container._initialized = True
            logger.info("PresentationContainer initialized")
        except Exception as e:
            logger.error(f"Failed to initialize PresentationContainer: {e}")
            raise
        return container

    @classmethod
    def create_minimal(cls) -> "PresentationContainer":
        """
        Create minimal container without theme files.

        Returns:
            Container with signal adapter and executor only
        """
        container = cls()
        container.signal_adapter = QtSignalAdapter()
        container.async_executor = AsyncExecutor()
        container._initialized = True
        return container

    def dispose(self) -> None:
        """Clean up resources."""
        if self.async_executor:
            self.async_executor.shutdown()
        if self.icon_manager:
            self.icon_manager.clear_cache()
        if self.theme_manager:
            self.theme_manager.clear_cache()
        self._initialized = False
        logger.info("PresentationContainer disposed")

    @property
    def is_initialized(self) -> bool:
        """Check if container is initialized."""
        return self._initialized


__all__ = ["PresentationContainer"]
