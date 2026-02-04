# src/iFactory/presentation/adapters/async_executor.py
"""
Async Executor - Thread pool for async operations with Qt integration.

Version: Fixed - No coroutine warnings on shutdown
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import (
    Awaitable,
    Callable,
    Generic,
    List,
    Optional,
    TypeVar,
)

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

T = TypeVar("T")

SLOW_OPERATION_THRESHOLD_MS = 3000
MAX_PENDING_FUTURES = 100


@dataclass(frozen=True, slots=True)
class AsyncResult(Generic[T]):
    """Result of an async operation."""

    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    elapsed_ms: float = 0.0

    @classmethod
    def ok(cls, value: T, elapsed_ms: float = 0.0) -> "AsyncResult[T]":
        return cls(success=True, value=value, elapsed_ms=elapsed_ms)

    @classmethod
    def err(cls, error: Exception, elapsed_ms: float = 0.0) -> "AsyncResult[T]":
        return cls(success=False, error=error, elapsed_ms=elapsed_ms)


class AsyncExecutor(QObject):
    """
    Executes async coroutines in a thread pool.

    Features:
    - Proper coroutine cleanup on shutdown (no warnings)
    - Configurable slow operation threshold
    - Thread-safe callbacks via Qt signals
    """

    _success_signal = Signal(object, object)
    _error_signal = Signal(object, object)

    def __init__(
        self,
        max_workers: int = 4,
        slow_threshold_ms: float = SLOW_OPERATION_THRESHOLD_MS,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AsyncExec",
        )
        self._is_running = True
        self._pending_futures: List[Future] = []
        self._operation_count = 0
        self._slow_threshold_ms = slow_threshold_ms
        self._signals_connected = True

        self._success_signal.connect(self._handle_success)
        self._error_signal.connect(self._handle_error)

    def _handle_success(self, callback: Callable, result: object) -> None:
        if not self._is_running:
            return
        try:
            if callback:
                callback(result)
        except Exception as e:
            logger.error(f"[AsyncExecutor] Success callback error: {e}")

    def _handle_error(self, callback: Callable, error: Exception) -> None:
        if not self._is_running:
            return
        try:
            if callback:
                callback(error)
        except Exception as e:
            logger.error(f"[AsyncExecutor] Error callback error: {e}")

    def execute(
        self,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        timeout: Optional[float] = None,
    ) -> bool:
        """
        Execute an async coroutine in the thread pool.

        Returns False if executor is shutting down.
        """
        if not self._is_running:
            # Close the coroutine properly to avoid "was never awaited" warning
            self._close_coroutine(coro)
            return False

        self._operation_count += 1
        operation_id = self._operation_count

        # Capture references for closure
        success_cb = on_success
        error_cb = on_error
        executor_ref = self
        timeout_secs = timeout
        slow_threshold = self._slow_threshold_ms
        the_coro = coro  # Capture the coroutine

        def worker():
            # Early exit if shutting down
            if not executor_ref._is_running:
                executor_ref._close_coroutine(the_coro)
                return

            start_time = datetime.now()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Double-check before running
                if not executor_ref._is_running:
                    return

                if timeout_secs:
                    result = loop.run_until_complete(asyncio.wait_for(the_coro, timeout=timeout_secs))
                else:
                    result = loop.run_until_complete(the_coro)

                # Check before callback
                if not executor_ref._is_running:
                    return

                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

                if success_cb and executor_ref._signals_connected:
                    executor_ref._success_signal.emit(success_cb, result)

                if elapsed_ms > slow_threshold:
                    logger.warning(f"[AsyncExecutor] Op #{operation_id} took {elapsed_ms:.0f}ms")

            except asyncio.TimeoutError:
                if executor_ref._is_running and error_cb and executor_ref._signals_connected:
                    error = TimeoutError(f"Operation timed out after {timeout_secs}s")
                    executor_ref._error_signal.emit(error_cb, error)

            except asyncio.CancelledError:
                pass  # Silent - expected during shutdown

            except Exception as e:
                if executor_ref._is_running and error_cb and executor_ref._signals_connected:
                    executor_ref._error_signal.emit(error_cb, e)

            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        future = self._executor.submit(worker)
        self._pending_futures.append(future)
        self._cleanup_futures()

        return True

    def _close_coroutine(self, coro: Awaitable) -> None:
        """Properly close a coroutine to avoid 'was never awaited' warning."""
        try:
            if hasattr(coro, "close"):
                coro.close()
        except Exception:
            pass

    def _cleanup_futures(self) -> None:
        """Remove completed futures from tracking list."""
        self._pending_futures = [f for f in self._pending_futures[-MAX_PENDING_FUTURES:] if not f.done()]

    def run(
        self,
        coro: Awaitable[T],
        callback: Optional[Callable[[T], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None,
        timeout: Optional[float] = None,
    ) -> bool:
        """Alias for execute()."""
        return self.execute(coro, callback, error_callback, timeout)

    @property
    def pending_count(self) -> int:
        """Number of pending operations."""
        self._cleanup_futures()
        return len(self._pending_futures)

    @property
    def is_running(self) -> bool:
        """Check if executor is running."""
        return self._is_running

    def shutdown(self, wait: bool = False, timeout: float = 1.0) -> None:
        """
        Shutdown executor with proper cleanup.

        Args:
            wait: If True, wait for pending operations (up to timeout)
            timeout: Max seconds to wait
        """
        if not self._is_running:
            return

        # Mark as not running FIRST to stop new tasks
        self._is_running = False
        self._signals_connected = False
        pending = self.pending_count

        logger.debug(f"[AsyncExecutor] Shutting down ({pending} pending)")

        # Disconnect signals to prevent callbacks during shutdown
        try:
            self._success_signal.disconnect()
        except (RuntimeError, TypeError):
            pass

        try:
            self._error_signal.disconnect()
        except (RuntimeError, TypeError):
            pass

        # Cancel pending futures
        for future in self._pending_futures:
            if not future.done():
                future.cancel()

        # Shutdown executor
        # Note: Don't use cancel_futures=True as it can cause warnings
        try:
            self._executor.shutdown(wait=wait, cancel_futures=False)
        except Exception as e:
            logger.debug(f"[AsyncExecutor] Shutdown error: {e}")

        self._pending_futures.clear()
        logger.debug("[AsyncExecutor] Shutdown complete")


__all__ = ["AsyncExecutor", "AsyncResult"]
