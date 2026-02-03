# src/application/config.py
"""
Application layer configuration and mediator setup.
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

from iFactory.application.mediator import (
    Mediator,
    LoggingBehavior,
    ValidationBehavior,
    CachingBehavior,
    MetricsBehavior,
)
from iFactory.application.commands.sync_commands import (
    SyncLatestStatusCommand,
    SyncLatestStatusHandler,
)
from iFactory.application.queries.device_queries import (
    GetDeviceQuery,
    GetDeviceHandler,
    GetAllDevicesQuery,
    GetAllDevicesHandler,
)

logger = logging.getLogger(__name__)


def configure_mediator(
    uow_factory: Callable,
    remote_source=None,
    id_mapper=None,
    enable_caching: bool = True,
    enable_metrics: bool = True,
) -> Mediator:
    """
    Configure the application mediator with all handlers and behaviors.

    Args:
        uow_factory: Factory for creating Unit of Work
        remote_source: Remote data source for sync operations
        id_mapper: Device ID mapper for display/remote conversion
        enable_caching: Whether to enable response caching
        enable_metrics: Whether to enable metrics collection

    Returns:
        Configured Mediator instance
    """
    mediator = Mediator()

    # ========================================================================
    # Register Behaviors (order matters!)
    # ========================================================================

    # 1. Metrics (outermost - times entire pipeline)
    if enable_metrics:
        mediator.use(MetricsBehavior())

    # 2. Logging
    mediator.use(LoggingBehavior(log_level=logging.DEBUG))

    # 3. Validation
    mediator.use(ValidationBehavior())

    # 4. Caching (before handler, after validation)
    if enable_caching:
        mediator.use(CachingBehavior())

    # ========================================================================
    # Register Query Handlers
    # ========================================================================

    mediator.register_handler_factory(
        GetDeviceQuery,
        lambda: GetDeviceHandler(uow_factory),
    )

    mediator.register_handler_factory(
        GetAllDevicesQuery,
        lambda: GetAllDevicesHandler(uow_factory),
    )

    # ========================================================================
    # Register Command Handlers
    # ========================================================================

    if remote_source:
        mediator.register_handler_factory(
            SyncLatestStatusCommand,
            lambda: SyncLatestStatusHandler(
                remote_source=remote_source,
                uow_factory=uow_factory,
                id_mapper=id_mapper,
            ),
        )

    logger.info("Mediator configured with handlers and behaviors")

    return mediator


__all__ = ["configure_mediator"]
