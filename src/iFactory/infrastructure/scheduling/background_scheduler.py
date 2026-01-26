"""
Infrastructure Job Scheduler.
Executes Application Use Cases in the background. Does not contain business knowledge.
"""

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """
    Pure infrastructure scheduler.
    Triggers Application Use Cases at regular intervals without coupling to what the Use Case does.
    """

    def __init__(self, interval_seconds: float):
        self._interval = interval_seconds
        self._running = False
        self._task: asyncio.Task | None = None

    def start(self, use_case_action: Callable[[], Awaitable[None]]) -> None:
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._job_loop(use_case_action))
        logger.info(f"BackgroundScheduler: Started with interval {self._interval}s.")

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

    async def _job_loop(self, use_case_action: Callable[[], Awaitable[None]]) -> None:
        while self._running:
            try:
                await use_case_action()
            except Exception as e:
                logger.error(f"BackgroundScheduler: Task execution failed: {e}")

            await asyncio.sleep(self._interval)
