"""
Infrastructure Job Scheduler.
Executes Application Use Cases (coroutines) at fixed intervals.
"""

import asyncio
import logging
from typing import Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class AsyncScheduler:
    """
    Background scheduler for repeated async tasks.
    Does not know about business logic; only executes provided callables.
    """

    def __init__(self, interval_seconds: float):
        self._interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

    def start(self, task_func: Callable[[], Awaitable[None]]) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._loop(task_func))
        logger.info(f"AsyncScheduler started. Interval: {self._interval}s")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("AsyncScheduler stopped.")

    async def _loop(self, task_func: Callable[[], Awaitable[None]]) -> None:
        while self._running:
            try:
                await task_func()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Scheduled task failed: {e}", exc_info=True)

            # Wait for interval or until cancelled
            try:
                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                break
