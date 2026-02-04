# src/iFactory/infrastructure/scheduling/task_scheduler.py
"""
Task Scheduler for background operations.

Features:
- BackgroundScheduler for simple interval-based tasks
- SyncScheduler for coordinated sync operations
- Graceful shutdown with timeout
- Error handling and retry logic
- Pause/resume support
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Awaitable, Callable, Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class SchedulerState(Enum):
    """Scheduler state."""

    STOPPED = auto()
    RUNNING = auto()
    PAUSED = auto()
    STOPPING = auto()


@dataclass
class SchedulerStats:
    """Statistics for a scheduler."""

    runs: int = 0
    successes: int = 0
    failures: int = 0
    last_run: Optional[datetime] = None
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    last_error: Optional[str] = None
    total_duration_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.runs == 0:
            return 1.0
        return self.successes / self.runs

    @property
    def avg_duration_ms(self) -> float:
        if self.runs == 0:
            return 0.0
        return self.total_duration_ms / self.runs

    def record_run(self, duration_ms: float, success: bool, error: Optional[str] = None) -> None:
        self.runs += 1
        self.last_run = datetime.now()
        self.total_duration_ms += duration_ms

        if success:
            self.successes += 1
            self.last_success = datetime.now()
        else:
            self.failures += 1
            self.last_failure = datetime.now()
            self.last_error = error

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runs": self.runs,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": f"{self.success_rate:.2%}",
            "avg_duration_ms": f"{self.avg_duration_ms:.1f}",
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "last_error": self.last_error,
        }


class BackgroundScheduler:
    """
    Infrastructure Service: Executes async tasks at fixed intervals.

    Features:
    - Configurable interval
    - Pause/resume support
    - Graceful shutdown
    - Error handling with statistics
    - Jitter to prevent thundering herd

    Usage:
        scheduler = BackgroundScheduler(interval_seconds=3.0)

        async def my_task():
            await do_work()

        scheduler.start(my_task)

        # Later...
        await scheduler.stop()
    """

    __slots__ = (
        "_interval",
        "_jitter",
        "_state",
        "_task",
        "_action",
        "_stats",
        "_stop_event",
        "_name",
    )

    def __init__(
        self,
        interval_seconds: float = 3.0,
        jitter: float = 0.0,
        name: str = "BackgroundScheduler",
    ) -> None:
        """
        Initialize scheduler.

        Args:
            interval_seconds: Time between task runs
            jitter: Random jitter (0-1) to add to interval
            name: Name for logging
        """
        self._interval = max(0.1, interval_seconds)
        self._jitter = max(0.0, min(1.0, jitter))
        self._state = SchedulerState.STOPPED
        self._task: Optional[asyncio.Task] = None
        self._action: Optional[Callable[[], Awaitable[None]]] = None
        self._stats = SchedulerStats()
        self._stop_event = asyncio.Event()
        self._name = name

    @property
    def is_running(self) -> bool:
        """Check if scheduler is actively running."""
        return self._state == SchedulerState.RUNNING

    @property
    def is_paused(self) -> bool:
        """Check if scheduler is paused."""
        return self._state == SchedulerState.PAUSED

    @property
    def state(self) -> SchedulerState:
        """Get current scheduler state."""
        return self._state

    @property
    def interval(self) -> float:
        """Get current interval."""
        return self._interval

    @property
    def stats(self) -> SchedulerStats:
        """Get scheduler statistics."""
        return self._stats

    def set_interval(self, seconds: float) -> None:
        """Update the sync interval."""
        self._interval = max(0.1, seconds)
        logger.info(f"[{self._name}] Interval updated to {self._interval}s")

    def start(self, action: Callable[[], Awaitable[None]]) -> None:
        """
        Start the scheduler with the given action.

        Args:
            action: Async function to execute on each interval
        """
        if self._state in (SchedulerState.RUNNING, SchedulerState.PAUSED):
            logger.warning(f"[{self._name}] Already running")
            return

        self._action = action
        self._state = SchedulerState.RUNNING
        self._stop_event.clear()
        self._task = asyncio.create_task(self._job_loop())

        logger.info(f"[{self._name}] Started (interval: {self._interval}s)")

    def pause(self) -> None:
        """Pause the scheduler without stopping it."""
        if self._state == SchedulerState.RUNNING:
            self._state = SchedulerState.PAUSED
            logger.debug(f"[{self._name}] Paused")

    def resume(self) -> None:
        """Resume the paused scheduler."""
        if self._state == SchedulerState.PAUSED:
            self._state = SchedulerState.RUNNING
            logger.debug(f"[{self._name}] Resumed")

    async def stop(self, timeout: float = 5.0) -> None:
        """
        Stop the scheduler gracefully.

        Args:
            timeout: Maximum time to wait for current task to complete
        """
        if self._state == SchedulerState.STOPPED:
            return

        self._state = SchedulerState.STOPPING
        self._stop_event.set()

        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"[{self._name}] Stop timed out, cancelling")
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass
            except asyncio.CancelledError:
                pass
            finally:
                self._task = None

        self._state = SchedulerState.STOPPED
        logger.info(f"[{self._name}] Stopped")

    async def run_once(self) -> bool:
        """
        Run the action once immediately.

        Returns:
            True if action succeeded
        """
        if not self._action:
            return False

        start = asyncio.get_event_loop().time()
        try:
            await self._action()
            duration_ms = (asyncio.get_event_loop().time() - start) * 1000
            self._stats.record_run(duration_ms, success=True)
            return True
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start) * 1000
            self._stats.record_run(duration_ms, success=False, error=str(e))
            logger.error(f"[{self._name}] Task failed: {e}")
            return False

    async def _job_loop(self) -> None:
        """Main job loop."""
        import random

        while not self._stop_event.is_set():
            if self._state == SchedulerState.RUNNING and self._action:
                await self.run_once()

            # Calculate sleep with optional jitter
            sleep_time = self._interval
            if self._jitter > 0:
                sleep_time += random.uniform(0, self._interval * self._jitter)

            # Use wait_for with stop_event to allow quick shutdown
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=sleep_time,
                )
                # Stop event was set
                break
            except asyncio.TimeoutError:
                # Normal timeout - continue loop
                pass


class SyncScheduler:
    """
    Specialized scheduler for coordinated sync operations.

    Manages multiple schedulers with different intervals for:
    - Latest status sync (fast, frequent)
    - History sync (slower, less frequent)
    - Availability sync (periodic)

    Usage:
        scheduler = SyncScheduler(
            latest_interval=3.0,
            history_interval=30.0,
        )

        scheduler.set_latest_action(sync_latest)
        scheduler.set_history_action(sync_history)

        scheduler.start()

        # Later...
        await scheduler.stop()
    """

    __slots__ = (
        "_latest_scheduler",
        "_history_scheduler",
        "_availability_scheduler",
    )

    def __init__(
        self,
        latest_interval: float = 3.0,
        history_interval: float = 30.0,
        availability_interval: float = 60.0,
    ) -> None:
        """
        Initialize sync scheduler.

        Args:
            latest_interval: Interval for latest status sync
            history_interval: Interval for history sync
            availability_interval: Interval for availability sync
        """
        self._latest_scheduler = BackgroundScheduler(
            latest_interval,
            name="LatestSync",
        )
        self._history_scheduler = BackgroundScheduler(
            history_interval,
            jitter=0.1,
            name="HistorySync",
        )
        self._availability_scheduler = BackgroundScheduler(
            availability_interval,
            jitter=0.2,
            name="AvailabilitySync",
        )

    @property
    def is_running(self) -> bool:
        """Check if any scheduler is running."""
        return self._latest_scheduler.is_running or self._history_scheduler.is_running or self._availability_scheduler.is_running

    def set_latest_action(self, action: Callable[[], Awaitable[None]]) -> None:
        """Set the action for latest status sync."""
        self._latest_scheduler._action = action

    def set_history_action(self, action: Callable[[], Awaitable[None]]) -> None:
        """Set the action for history sync."""
        self._history_scheduler._action = action

    def set_availability_action(self, action: Callable[[], Awaitable[None]]) -> None:
        """Set the action for availability sync."""
        self._availability_scheduler._action = action

    def start(self) -> None:
        """Start all configured schedulers."""
        if self._latest_scheduler._action:
            self._latest_scheduler.start(self._latest_scheduler._action)
        if self._history_scheduler._action:
            self._history_scheduler.start(self._history_scheduler._action)
        if self._availability_scheduler._action:
            self._availability_scheduler.start(self._availability_scheduler._action)

    def start_latest_only(self) -> None:
        """Start only latest status scheduler."""
        if self._latest_scheduler._action:
            self._latest_scheduler.start(self._latest_scheduler._action)

    def start_history_only(self) -> None:
        """Start only history scheduler."""
        if self._history_scheduler._action:
            self._history_scheduler.start(self._history_scheduler._action)

    async def stop(self, timeout: float = 5.0) -> None:
        """Stop all schedulers."""
        await asyncio.gather(
            self._latest_scheduler.stop(timeout),
            self._history_scheduler.stop(timeout),
            self._availability_scheduler.stop(timeout),
            return_exceptions=True,
        )

    def pause(self) -> None:
        """Pause all schedulers."""
        self._latest_scheduler.pause()
        self._history_scheduler.pause()
        self._availability_scheduler.pause()

    def resume(self) -> None:
        """Resume all schedulers."""
        self._latest_scheduler.resume()
        self._history_scheduler.resume()
        self._availability_scheduler.resume()

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all schedulers."""
        return {
            "latest": self._latest_scheduler.stats.to_dict(),
            "history": self._history_scheduler.stats.to_dict(),
            "availability": self._availability_scheduler.stats.to_dict(),
        }


__all__ = [
    "BackgroundScheduler",
    "SyncScheduler",
    "SchedulerState",
    "SchedulerStats",
]
