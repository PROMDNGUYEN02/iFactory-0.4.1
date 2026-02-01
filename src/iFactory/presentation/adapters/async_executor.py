"""
Async Executor - Fixed with proper shutdown handling.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Awaitable, Callable, Optional, TypeVar, Any, List

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncExecutor(QObject):
    """Executes async coroutines in a thread pool and calls back on main thread."""

    # Internal signals for thread-safe callback execution
    _success_signal = Signal(object, object)  # (callback, result)
    _error_signal = Signal(object, object)  # (callback, error)

    def __init__(self, max_workers: int = 4, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AsyncExecutor",
        )
        self._is_running = True
        self._pending_futures: List[Future] = []

        # Connect internal signals to handler slots
        self._success_signal.connect(self._handle_success)
        self._error_signal.connect(self._handle_error)

    def _handle_success(self, callback: Callable, result: Any) -> None:
        """Handle success callback on main thread."""
        if not self._is_running:
            return
        try:
            if callback:
                callback(result)
        except Exception as e:
            logger.error(f"[AsyncExecutor] Success callback failed: {e}")

    def _handle_error(self, callback: Callable, error: Any) -> None:
        """Handle error callback on main thread."""
        if not self._is_running:
            return
        try:
            if callback:
                callback(error)
        except Exception as e:
            logger.error(f"[AsyncExecutor] Error callback failed: {e}")

    def execute(
        self,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        if not self._is_running:
            logger.debug("AsyncExecutor is shutting down, task rejected")
            return

        # Capture callbacks
        success_cb = on_success
        error_cb = on_error
        executor = self  # Capture self reference

        def worker():
            if not executor._is_running:
                return

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)

                # Only emit if still running
                if executor._is_running and success_cb:
                    executor._success_signal.emit(success_cb, result)

            except Exception as e:
                if executor._is_running:
                    logger.error(f"[AsyncExecutor] Async task failed: {e}")
                    if error_cb:
                        executor._error_signal.emit(error_cb, e)

            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        future = self._executor.submit(worker)
        self._pending_futures.append(future)

        # Clean up completed futures
        self._pending_futures = [f for f in self._pending_futures if not f.done()]

    def run(
        self,
        coro: Awaitable[T],
        callback: Optional[Callable[[T], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self.execute(coro, callback, error_callback)

    def shutdown(self, wait: bool = False, timeout: float = 0.5) -> None:
        """Shutdown executor, optionally waiting for pending tasks."""
        self._is_running = False

        # Disconnect signals to prevent callbacks after shutdown
        try:
            self._success_signal.disconnect()
            self._error_signal.disconnect()
        except RuntimeError:
            pass

        # Cancel pending futures
        for future in self._pending_futures:
            if not future.done():
                future.cancel()

        # Shutdown executor
        self._executor.shutdown(wait=wait, cancel_futures=True)
        self._pending_futures.clear()

        logger.debug("AsyncExecutor shutdown complete")


__all__ = ["AsyncExecutor"]
