# src/iFactory/presentation/adapters/async_executor.py
"""
Async Executor - Thread pool for async operations with Qt integration.

Features:
- Executes async coroutines in background threads
- Callbacks on Qt main thread via signals
- Configurable timeout per operation
- Graceful shutdown with operation tracking
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


# ============================================================================
# Result Wrapper
# ============================================================================


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


# ============================================================================
# Async Executor
# ============================================================================


class AsyncExecutor(QObject):
    """
    Executes async coroutines in a thread pool.

    Callbacks are invoked on the Qt main thread via signals.

    Features:
    - Configurable worker pool size
    - Optional timeout per operation
    - Operation tracking for cleanup
    - Graceful shutdown

    Usage:
        executor = AsyncExecutor(max_workers=4)

        executor.execute(
            fetch_data(),
            on_success=lambda result: print(result),
            on_error=lambda e: print(f"Error: {e}"),
            timeout=30.0,
        )

        # Cleanup
        executor.shutdown()
    """

    # Internal signals for thread-safe callbacks
    _success_signal = Signal(object, object)  # (callback, result)
    _error_signal = Signal(object, object)  # (callback, error)

    def __init__(
        self,
        max_workers: int = 4,
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

        # Connect internal signals
        self._success_signal.connect(self._handle_success)
        self._error_signal.connect(self._handle_error)

    def _handle_success(self, callback: Callable, result: AsyncResult) -> None:
        """Handle success callback on main thread."""
        if not self._is_running:
            return
        try:
            if callback:
                # Pass just the value for backward compatibility
                callback(result.value if isinstance(result, AsyncResult) else result)
        except Exception as e:
            logger.error(f"[AsyncExecutor] Success callback error: {e}")

    def _handle_error(self, callback: Callable, error: Exception) -> None:
        """Handle error callback on main thread."""
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

        Args:
            coro: Async coroutine to execute
            on_success: Callback for successful result (called on main thread)
            on_error: Callback for errors (called on main thread)
            timeout: Optional timeout in seconds

        Returns:
            True if task was submitted, False if executor is shutting down
        """
        if not self._is_running:
            logger.debug("[AsyncExecutor] Shutting down, task rejected")
            return False

        self._operation_count += 1
        operation_id = self._operation_count

        # Capture references
        success_cb = on_success
        error_cb = on_error
        executor_ref = self
        timeout_secs = timeout

        def worker():
            if not executor_ref._is_running:
                return

            start_time = datetime.now()
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                # Apply timeout if specified
                if timeout_secs:
                    result = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout_secs))
                else:
                    result = loop.run_until_complete(coro)

                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

                if executor_ref._is_running and success_cb:
                    executor_ref._success_signal.emit(success_cb, result)

                if elapsed_ms > 5000:
                    logger.warning(f"[AsyncExecutor] Op #{operation_id} took {elapsed_ms:.0f}ms")

            except asyncio.TimeoutError:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                if executor_ref._is_running:
                    error = TimeoutError(f"Operation timed out after {timeout_secs}s")
                    logger.warning(f"[AsyncExecutor] Op #{operation_id} timed out")
                    if error_cb:
                        executor_ref._error_signal.emit(error_cb, error)

            except asyncio.CancelledError:
                logger.debug(f"[AsyncExecutor] Op #{operation_id} cancelled")

            except Exception as e:
                if executor_ref._is_running:
                    logger.error(f"[AsyncExecutor] Op #{operation_id} failed: {e}")
                    if error_cb:
                        executor_ref._error_signal.emit(error_cb, e)

            finally:
                try:
                    loop.close()
                except Exception:
                    pass

        future = self._executor.submit(worker)
        self._pending_futures.append(future)

        # Clean up completed futures periodically
        self._cleanup_futures()

        return True

    def _cleanup_futures(self) -> None:
        """Remove completed futures from tracking list."""
        self._pending_futures = [f for f in self._pending_futures if not f.done()]

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
        Shutdown executor.

        Args:
            wait: If True, wait for pending operations
            timeout: Max seconds to wait when wait=True
        """
        if not self._is_running:
            return

        self._is_running = False
        logger.debug(f"[AsyncExecutor] Shutting down ({self.pending_count} pending)")

        # Disconnect signals to prevent callbacks
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
        try:
            self._executor.shutdown(wait=wait, cancel_futures=True)
        except Exception as e:
            logger.debug(f"[AsyncExecutor] Shutdown error: {e}")

        self._pending_futures.clear()
        logger.debug("[AsyncExecutor] Shutdown complete")


__all__ = ["AsyncExecutor", "AsyncResult"]
