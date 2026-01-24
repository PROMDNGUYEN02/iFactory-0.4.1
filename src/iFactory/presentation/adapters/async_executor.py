"""
Async Executor - Run async operations in Qt context.

Provides a bridge between asyncio and Qt's event loop.
"""

from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Optional, TypeVar
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AsyncExecutor(QObject):
    """
    Execute async operations from Qt context.

    Features:
        - Run coroutines from sync Qt code
        - Periodic async task scheduling
        - Error handling with signals
        - Graceful shutdown

    Example:
        executor = AsyncExecutor()
        executor.run(some_async_function())
    """

    task_completed = Signal(object)
    task_failed = Signal(str)

    def __init__(self, max_workers: int = 4, parent: Optional[QObject] = None):
        """
        Initialize executor.

        Args:
            max_workers: Maximum thread pool workers
            parent: Qt parent object
        """
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._periodic_timers: dict[str, QTimer] = {}
        self._running = True

    def run(
        self, coro: Awaitable[T], callback: Optional[Callable[[T], None]] = None, error_callback: Optional[Callable[[Exception], None]] = None
    ) -> None:
        """
        Run coroutine asynchronously.

        Args:
            coro: Coroutine to execute
            callback: Success callback
            error_callback: Error callback
        """
        if not self._running:
            logger.warning("Executor is shut down")
            return

        def _run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(coro)
                if callback:
                    QTimer.singleShot(0, lambda: callback(result))
                self.task_completed.emit(result)
                return result
            except Exception as e:
                logger.error(f"Async task failed: {e}")
                if error_callback:
                    QTimer.singleShot(0, lambda: error_callback(e))
                self.task_failed.emit(str(e))
                return None
            finally:
                loop.close()

        self._executor.submit(_run_in_thread)

    def run_sync(self, coro: Awaitable[T]) -> Optional[T]:
        """
        Run coroutine synchronously (blocking).

        Warning: This blocks the calling thread. Use with caution in UI thread.

        Args:
            coro: Coroutine to execute

        Returns:
            Result or None on error
        """
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop.run_until_complete(coro)
        except Exception as e:
            logger.error(f"Sync task failed: {e}")
            return None
        finally:
            loop.close()

    def schedule_periodic(self, task_id: str, coro_factory: Callable[[], Awaitable[Any]], interval_ms: int, immediate: bool = False) -> None:
        """
        Schedule periodic async task.

        Args:
            task_id: Unique task identifier
            coro_factory: Factory function creating coroutine
            interval_ms: Interval in milliseconds
            immediate: Run immediately before starting timer
        """
        self.cancel_periodic(task_id)
        timer = QTimer(self)
        timer.setInterval(interval_ms)
        timer.timeout.connect(lambda: self.run(coro_factory()))
        self._periodic_timers[task_id] = timer
        if immediate:
            self.run(coro_factory())
        timer.start()
        logger.debug(f"Scheduled periodic task: {task_id} ({interval_ms}ms)")

    def cancel_periodic(self, task_id: str) -> bool:
        """
        Cancel periodic task.

        Args:
            task_id: Task identifier

        Returns:
            True if cancelled
        """
        if task_id in self._periodic_timers:
            self._periodic_timers[task_id].stop()
            self._periodic_timers[task_id].deleteLater()
            del self._periodic_timers[task_id]
            return True
        return False

    def cancel_all_periodic(self) -> None:
        """Cancel all periodic tasks."""
        for task_id in list(self._periodic_timers.keys()):
            self.cancel_periodic(task_id)

    def shutdown(self, wait: bool = True) -> None:
        """
        Shutdown executor.

        Args:
            wait: Wait for pending tasks
        """
        self._running = False
        self.cancel_all_periodic()
        self._executor.shutdown(wait=wait)
        logger.info("AsyncExecutor shut down")

    @property
    def is_running(self) -> bool:
        """Check if executor is running."""
        return self._running
