"""
Infrastructure: Task Scheduler.
Generic background job runner using asyncio.
"""

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """
    Executes a given async callable at fixed intervals.
    Agnostic to the actual task performed.
    """

    def __init__(self, interval_seconds: float):
        self._interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self, action: Callable[[], Awaitable[None]]) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._job_loop(action))
        logger.info(f"BackgroundScheduler: Started (Interval: {self._interval}s).")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("BackgroundScheduler: Stopped.")

    async def _job_loop(self, action: Callable[[], Awaitable[None]]) -> None:
        while self._running:
            try:
                await action()
            except Exception as e:
                logger.error(f"BackgroundScheduler: Job failed: {e}")

            await asyncio.sleep(self._interval)
