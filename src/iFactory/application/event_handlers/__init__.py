# File: application/event_handlers/__init__.py
"""
Domain Event Handlers.

These handlers react to domain events and perform side effects
like notifications, metrics, audit logging, etc.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from iFactory.domain.events.device_events import StatusChangedEvent

logger = logging.getLogger(__name__)


async def log_status_changes(event: "StatusChangedEvent") -> None:
    """
    Handler: Log all status changes for audit trail.
    """
    logger.info(
        "AUDIT: Device %s changed from %s to %s at %s",
        event.equipment_code.value,
        event.previous_status.name,
        event.new_status.name,
        event.occurred_at.isoformat(),
    )


async def track_downtime_metrics(event: "StatusChangedEvent") -> None:
    """
    Handler: Track downtime metrics.

    Could integrate with metrics systems like Prometheus, DataDog, etc.
    """
    if event.was_downtime_start:
        logger.info(
            "METRIC: Downtime started for %s (status: %s)",
            event.equipment_code.value,
            event.new_status.name,
        )
        # await metrics.increment("device.downtime.started", tags={...})

    elif event.was_downtime_end:
        logger.info(
            "METRIC: Downtime ended for %s",
            event.equipment_code.value,
        )
        # await metrics.increment("device.downtime.ended", tags={...})


async def notify_on_alarm(event: "StatusChangedEvent") -> None:
    """
    Handler: Send notifications when devices enter ALARM state.

    Could integrate with email, SMS, Slack, etc.
    """
    from iFactory.domain.enums.machine_status import MachineStatus

    if event.new_status == MachineStatus.ALARM:
        logger.warning(
            "ALERT: Device %s entered ALARM state! Previous: %s",
            event.equipment_code.value,
            event.previous_status.name,
        )
        # await notification_service.send_alert(...)


def register_event_handlers() -> None:
    """
    Register all domain event handlers.

    Call this during application bootstrap.
    """
    from iFactory.domain.common.event_dispatcher import get_event_dispatcher
    from iFactory.domain.events.device_events import StatusChangedEvent

    dispatcher = get_event_dispatcher()

    # Register handlers for StatusChangedEvent
    dispatcher.register(StatusChangedEvent, log_status_changes)
    dispatcher.register(StatusChangedEvent, track_downtime_metrics)
    dispatcher.register(StatusChangedEvent, notify_on_alarm)

    logger.info("Domain event handlers registered")


__all__ = [
    "log_status_changes",
    "track_downtime_metrics",
    "notify_on_alarm",
    "register_event_handlers",
]
