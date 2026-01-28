import asyncio
import logging
from typing import Callable, Awaitable, Optional

logger = logging.getLogger(__name__)


class BackgroundScheduler:
    """
    Infrastructure Service: Executes async tasks at fixed intervals.
    Totally agnostic to the domain or application logic of the task.
    """

    def __init__(self, interval_seconds: float):
        self._interval = interval_seconds
        self._running = False
        self._task: Optional[asyncio.Task] = None

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
