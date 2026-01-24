"""
Infrastructure Layer Lifecycle Manager.

Manages initialization and cleanup of infrastructure components.
This is separate from domain repository contracts.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Sequence

from ...application.interfaces.lifecycle_aware import LifecycleAware

if TYPE_CHECKING:
    from .device_repository_impl import SqliteDeviceRepository
    from .status_repository_impl import SqliteStatusRepository
    from .input_repository_impl import SqliteInputRepository
    from .sync_metadata_repository_impl import SqliteSyncMetadataRepository

__all__ = ["InfrastructureLifecycleManager"]

logger = logging.getLogger(__name__)


class InfrastructureLifecycleManager:
    """
    Manages lifecycle of infrastructure components.

    Trách nhiệm:
        - Initialize all infrastructure components in order
        - Clean up resources during shutdown
        - Track initialization state

    Note: This is separate from domain repository interfaces
    which define only data access contracts.
    """

    __slots__ = ("_components", "_initialized")

    def __init__(self):
        """Initialize lifecycle manager."""
        self._components: Sequence[LifecycleAware] = []
        self._initialized = False

    def register(self, component: LifecycleAware) -> None:
        """
        Register an infrastructure component.

        Args:
            component: Component with lifecycle (repository, cache, etc.)
        """
        self._components = [*self._components, component]

    def register_many(self, components: Sequence[LifecycleAware]) -> None:
        """
        Register multiple infrastructure components.

        Args:
            components: List of components with lifecycle
        """
        self._components = [*self._components, *components]

    async def initialize_all(self) -> None:
        """
        Initialize all registered components.

        Raises:
            Exception: If any component fails to initialize
        """
        if self._initialized:
            logger.warning("[Lifecycle] Already initialized")
            return

        logger.info(f"[Lifecycle] Initializing {len(self._components)} components")
        for component in self._components:
            try:
                await component.initialize()
                logger.debug(f"[Lifecycle] Initialized {component.__class__.__name__}")
            except Exception as e:
                logger.error(f"[Lifecycle] Failed to initialize {component.__class__.__name__}: {e}", exc_info=True)
                raise

        self._initialized = True
        logger.info("[Lifecycle] All components initialized")

    async def dispose_all(self) -> None:
        """
        Clean up all registered components.

        Logs and continues on errors (best effort cleanup).
        """
        if not self._initialized:
            logger.debug("[Lifecycle] Not initialized, skipping dispose")
            return

        logger.info(f"[Lifecycle] Disposing {len(self._components)} components")
        for component in reversed(self._components):  # Reverse order for cleanup
            try:
                await component.dispose()
                logger.debug(f"[Lifecycle] Disposed {component.__class__.__name__}")
            except Exception as e:
                logger.error(f"[Lifecycle] Failed to dispose {component.__class__.__name__}: {e}", exc_info=True)

        self._initialized = False
        logger.info("[Lifecycle] All components disposed")

    @property
    def is_initialized(self) -> bool:
        """Check if lifecycle manager has been initialized."""
        return self._initialized

    @property
    def component_count(self) -> int:
        """Get number of registered components."""
        return len(self._components)
