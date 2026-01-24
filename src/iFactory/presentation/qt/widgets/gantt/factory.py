"""
Gantt manager factory functions - UI Infrastructure.
"""

from __future__ import annotations
from typing import Optional
from .manager import GanttManager, GanttConfig

__all__ = ["create_gantt_manager", "create_gantt_manager_async"]


def create_gantt_manager(
    db: Optional[Any] = None,
    default_days_back: int = 1,
    show_summary: bool = False,
    parent: Optional[Any] = None,
) -> GanttManager:
    """
    Factory function to create GanttManager.

    Args:
        db: Database orchestrator
        default_days_back: Default days to query
        show_summary: Show summary statistics
        parent: Qt parent

    Returns:
        Configured GanttManager
    """
    config = GanttConfig(
        show_summary=show_summary, default_range_hours=default_days_back * 24
    )
    return GanttManager(db=db, config=config, parent=parent)


async def create_gantt_manager_async(
    db: Optional[Any] = None,
    default_days_back: int = 1,
    show_summary: bool = False,
    parent: Optional[Any] = None,
) -> GanttManager:
    """
    Async factory that also initializes the manager.

    Args:
        db: Database orchestrator
        default_days_back: Default days to query
        show_summary: Show summary statistics
        parent: Qt parent

    Returns:
        Initialized GanttManager
    """
    manager = create_gantt_manager(db, default_days_back, show_summary, parent)
    await manager.initialize()
    return manager
