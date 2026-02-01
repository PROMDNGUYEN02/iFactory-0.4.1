# File: infrastructure/scheduling/task_scheduler.py
"""
Task Scheduler.
Manages background sync tasks with configurable intervals.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """
    Infrastructure Service: Executes async tasks at fixed intervals.
    """

    def __init__(self, interval_seconds: float = 3.0):
        self._interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._paused = False

    @property
    def is_running(self) -> bool:
        return self._running and not self._paused

    @property
    def interval(self) -> float:
        return self._interval

    def set_interval(self, seconds: float) -> None:
        """Update the sync interval."""
        self._interval = max(1.0, seconds)
        logger.info(f"[BackgroundScheduler] Interval updated to {self._interval}s")

    def start(self, action: Callable[[], Awaitable[None]]) -> None:
        """Start the scheduler with the given action."""
        if self._running:
            return

        self._running = True
        self._paused = False
        self._task = asyncio.create_task(self._job_loop(action))
        logger.info(f"[BackgroundScheduler] Started (interval: {self._interval}s)")

    def pause(self) -> None:
        """Pause the scheduler without stopping it."""
        self._paused = True
        logger.debug("[BackgroundScheduler] Paused")

    def resume(self) -> None:
        """Resume the paused scheduler."""
        self._paused = False
        logger.debug("[BackgroundScheduler] Resumed")

    async def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("[BackgroundScheduler] Stopped")

    async def _job_loop(self, action: Callable[[], Awaitable[None]]) -> None:
        """Main job loop."""
        while self._running:
            if not self._paused:
                try:
                    await action()
                except Exception as e:
                    logger.error(f"[BackgroundScheduler] Job failed: {e}")

            await asyncio.sleep(self._interval)


class SyncScheduler:
    """
    Specialized scheduler for sync operations.
    Manages both latest status and history sync with different intervals.
    """

    def __init__(
        self,
        latest_interval: float = 3.0,
        history_interval: float = 3.0,
    ):
        self._latest_scheduler = BackgroundScheduler(latest_interval)
        self._history_scheduler = BackgroundScheduler(history_interval)

        self._latest_action: Optional[Callable[[], Awaitable[None]]] = None
        self._history_action: Optional[Callable[[], Awaitable[None]]] = None

    def set_latest_action(self, action: Callable[[], Awaitable[None]]) -> None:
        """Set the action for latest status sync."""
        self._latest_action = action

    def set_history_action(self, action: Callable[[], Awaitable[None]]) -> None:
        """Set the action for history sync."""
        self._history_action = action

    def start(self) -> None:
        """Start both schedulers."""
        if self._latest_action:
            self._latest_scheduler.start(self._latest_action)
        if self._history_action:
            self._history_scheduler.start(self._history_action)

    def start_latest_only(self) -> None:
        """Start only latest status scheduler."""
        if self._latest_action:
            self._latest_scheduler.start(self._latest_action)

    def start_history_only(self) -> None:
        """Start only history scheduler."""
        if self._history_action:
            self._history_scheduler.start(self._history_action)

    async def stop(self) -> None:
        """Stop both schedulers."""
        await self._latest_scheduler.stop()
        await self._history_scheduler.stop()

    def pause(self) -> None:
        """Pause both schedulers."""
        self._latest_scheduler.pause()
        self._history_scheduler.pause()

    def resume(self) -> None:
        """Resume both schedulers."""
        self._latest_scheduler.resume()
        self._history_scheduler.resume()


__all__ = ["BackgroundScheduler", "SyncScheduler"]
