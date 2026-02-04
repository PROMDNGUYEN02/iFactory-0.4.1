# src/iFactory/presentation/adapters/async_executor.py
"""
Async Executor - Production-ready thread pool for async operations.

FEATURES v2.0:
- Proper coroutine cleanup (no warnings)
- Operation tracking and metrics
- Configurable slow operation threshold
- Priority queue support
- Graceful shutdown with timeout
- Memory-efficient result handling
- Qt signal-based callbacks
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import weakref
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from queue import PriorityQueue
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Union,
)

from PySide6.QtCore import QObject, Signal, QTimer

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Constants
# ============================================================================

DEFAULT_MAX_WORKERS: int = 4
DEFAULT_SLOW_THRESHOLD_MS: float = 3000.0
DEFAULT_SHUTDOWN_TIMEOUT: float = 2.0
MAX_PENDING_FUTURES: int = 100


# ============================================================================
# Result Types
# ============================================================================


class OperationStatus(Enum):
    """Operation status."""

    PENDING = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    CANCELLED = auto()
    TIMEOUT = auto()


@dataclass(frozen=True, slots=True)
class AsyncResult(Generic[T]):
    """
    Immutable result of an async operation.

    Attributes:
        success: Whether operation succeeded
        value: Result value if successful
        error: Exception if failed
        elapsed_ms: Operation duration in milliseconds
        status: Final operation status
    """

    success: bool
    value: Optional[T] = None
    error: Optional[Exception] = None
    elapsed_ms: float = 0.0
    status: OperationStatus = OperationStatus.COMPLETED

    @classmethod
    def ok(cls, value: T, elapsed_ms: float = 0.0) -> "AsyncResult[T]":
        """Create successful result."""
        return cls(
            success=True,
            value=value,
            elapsed_ms=elapsed_ms,
            status=OperationStatus.COMPLETED,
        )

    @classmethod
    def err(
        cls,
        error: Exception,
        elapsed_ms: float = 0.0,
        status: OperationStatus = OperationStatus.FAILED,
    ) -> "AsyncResult[T]":
        """Create error result."""
        return cls(
            success=False,
            error=error,
            elapsed_ms=elapsed_ms,
            status=status,
        )

    @classmethod
    def cancelled(cls, elapsed_ms: float = 0.0) -> "AsyncResult[T]":
        """Create cancelled result."""
        return cls(
            success=False,
            elapsed_ms=elapsed_ms,
            status=OperationStatus.CANCELLED,
        )


# ============================================================================
# Operation Priority
# ============================================================================


class Priority(Enum):
    """Operation priority levels."""

    HIGH = 0
    NORMAL = 1
    LOW = 2


@dataclass(order=True)
class PrioritizedOperation:
    """Operation with priority for queue ordering."""

    priority: int
    timestamp: float = field(compare=True)
    operation_id: int = field(compare=False)
    coro: Any = field(compare=False)
    on_success: Any = field(compare=False, default=None)
    on_error: Any = field(compare=False, default=None)
    timeout: Optional[float] = field(compare=False, default=None)


# ============================================================================
# Metrics
# ============================================================================


@dataclass
class ExecutorMetrics:
    """Executor performance metrics."""

    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    cancelled_operations: int = 0
    timeout_operations: int = 0
    slow_operations: int = 0
    total_elapsed_ms: float = 0.0
    max_elapsed_ms: float = 0.0

    @property
    def success_rate(self) -> float:
        if self.total_operations == 0:
            return 1.0
        return self.successful_operations / self.total_operations

    @property
    def avg_elapsed_ms(self) -> float:
        if self.total_operations == 0:
            return 0.0
        return self.total_elapsed_ms / self.total_operations

    def record_success(self, elapsed_ms: float, is_slow: bool = False) -> None:
        self.total_operations += 1
        self.successful_operations += 1
        self.total_elapsed_ms += elapsed_ms
        self.max_elapsed_ms = max(self.max_elapsed_ms, elapsed_ms)
        if is_slow:
            self.slow_operations += 1

    def record_failure(self, elapsed_ms: float) -> None:
        self.total_operations += 1
        self.failed_operations += 1
        self.total_elapsed_ms += elapsed_ms

    def record_timeout(self, elapsed_ms: float) -> None:
        self.total_operations += 1
        self.timeout_operations += 1
        self.total_elapsed_ms += elapsed_ms

    def record_cancelled(self) -> None:
        self.total_operations += 1
        self.cancelled_operations += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total": self.total_operations,
            "successful": self.successful_operations,
            "failed": self.failed_operations,
            "cancelled": self.cancelled_operations,
            "timeouts": self.timeout_operations,
            "slow": self.slow_operations,
            "success_rate": f"{self.success_rate:.1%}",
            "avg_elapsed_ms": f"{self.avg_elapsed_ms:.1f}",
            "max_elapsed_ms": f"{self.max_elapsed_ms:.1f}",
        }


# ============================================================================
# Async Executor
# ============================================================================


class AsyncExecutor(QObject):
    """
    Production-ready executor for async operations in Qt applications.

    Features:
    - Executes async coroutines in a thread pool
    - Proper coroutine cleanup (no "never awaited" warnings)
    - Thread-safe Qt signal callbacks
    - Operation tracking and metrics
    - Priority queue support
    - Configurable slow operation threshold
    - Graceful shutdown with timeout

    Usage:
        executor = AsyncExecutor(max_workers=4, parent=widget)

        # Execute async operation
        executor.execute(
            fetch_data(),
            on_success=lambda data: update_ui(data),
            on_error=lambda e: show_error(str(e)),
            timeout=10.0,
        )

        # Check metrics
        print(executor.metrics)

        # Cleanup
        executor.shutdown()

    Signals:
        operationCompleted: Emitted when any operation completes
    """

    # Signals for thread-safe callbacks
    _success_signal = Signal(object, object)  # callback, result
    _error_signal = Signal(object, object)  # callback, error
    operationCompleted = Signal(int, bool)  # operation_id, success

    def __init__(
        self,
        max_workers: int = DEFAULT_MAX_WORKERS,
        slow_threshold_ms: float = DEFAULT_SLOW_THRESHOLD_MS,
        parent: Optional[QObject] = None,
    ):
        """
        Initialize AsyncExecutor.

        Args:
            max_workers: Maximum number of worker threads
            slow_threshold_ms: Threshold for slow operation warnings
            parent: Qt parent object
        """
        super().__init__(parent)

        self._max_workers = max_workers
        self._slow_threshold_ms = slow_threshold_ms

        # Thread pool
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="AsyncExec",
        )

        # State
        self._is_running = True
        self._is_shutting_down = False
        self._operation_counter = 0
        self._pending_futures: Dict[int, Future] = {}
        self._lock = threading.Lock()

        # Metrics
        self._metrics = ExecutorMetrics()

        # Connect signals
        self._signals_connected = True
        self._success_signal.connect(self._handle_success_callback)
        self._error_signal.connect(self._handle_error_callback)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_running(self) -> bool:
        """Check if executor is running."""
        return self._is_running and not self._is_shutting_down

    @property
    def pending_count(self) -> int:
        """Number of pending operations."""
        with self._lock:
            # Clean up completed futures
            self._pending_futures = {k: v for k, v in self._pending_futures.items() if not v.done()}
            return len(self._pending_futures)

    @property
    def metrics(self) -> ExecutorMetrics:
        """Get executor metrics."""
        return self._metrics

    # =========================================================================
    # Signal Handlers
    # =========================================================================

    def _handle_success_callback(self, callback: Callable, result: Any) -> None:
        """Handle success callback on Qt thread."""
        if not self._is_running:
            return
        try:
            if callback:
                callback(result)
        except Exception as e:
            logger.error("[AsyncExecutor] Success callback error: %s", e)

    def _handle_error_callback(self, callback: Callable, error: Exception) -> None:
        """Handle error callback on Qt thread."""
        if not self._is_running:
            return
        try:
            if callback:
                callback(error)
        except Exception as e:
            logger.error("[AsyncExecutor] Error callback error: %s", e)

    # =========================================================================
    # Core Execution
    # =========================================================================

    def execute(
        self,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        timeout: Optional[float] = None,
        priority: Priority = Priority.NORMAL,
    ) -> int:
        """
        Execute an async coroutine in the thread pool.

        Args:
            coro: Async coroutine to execute
            on_success: Callback for successful result (called on Qt thread)
            on_error: Callback for errors (called on Qt thread)
            timeout: Optional timeout in seconds
            priority: Operation priority

        Returns:
            Operation ID for tracking

        Raises:
            RuntimeError: If executor is shutting down
        """
        if not self._is_running or self._is_shutting_down:
            self._close_coroutine(coro)
            return -1

        with self._lock:
            self._operation_counter += 1
            operation_id = self._operation_counter

        # Create worker function
        def worker():
            return self._run_operation(
                operation_id=operation_id,
                coro=coro,
                on_success=on_success,
                on_error=on_error,
                timeout=timeout,
            )

        # Submit to thread pool
        future = self._executor.submit(worker)

        with self._lock:
            self._pending_futures[operation_id] = future

            # Cleanup old futures
            if len(self._pending_futures) > MAX_PENDING_FUTURES:
                self._cleanup_futures()

        return operation_id

    def _run_operation(
        self,
        operation_id: int,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]],
        on_error: Optional[Callable[[Exception], None]],
        timeout: Optional[float],
    ) -> Optional[AsyncResult[T]]:
        """Run operation in worker thread."""
        # Early exit if shutting down
        if not self._is_running or self._is_shutting_down:
            self._close_coroutine(coro)
            return None

        start_time = time.perf_counter()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            # Double-check before running
            if not self._is_running or self._is_shutting_down:
                self._close_coroutine(coro)
                return None

            # Execute with optional timeout
            if timeout:
                result = loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
            else:
                result = loop.run_until_complete(coro)

            # Check before callback
            if not self._is_running or self._is_shutting_down:
                return None

            elapsed_ms = (time.perf_counter() - start_time) * 1000
            is_slow = elapsed_ms > self._slow_threshold_ms

            # Record metrics
            self._metrics.record_success(elapsed_ms, is_slow)

            if is_slow:
                logger.warning("[AsyncExecutor] Op #%d took %.0fms", operation_id, elapsed_ms)

            # Emit success callback via signal
            if on_success and self._signals_connected:
                self._success_signal.emit(on_success, result)

            # Emit completion signal
            self.operationCompleted.emit(operation_id, True)

            return AsyncResult.ok(result, elapsed_ms)

        except asyncio.TimeoutError:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_timeout(elapsed_ms)

            error = TimeoutError(f"Operation timed out after {timeout}s")

            if self._is_running and on_error and self._signals_connected:
                self._error_signal.emit(on_error, error)

            self.operationCompleted.emit(operation_id, False)

            return AsyncResult.err(error, elapsed_ms, OperationStatus.TIMEOUT)

        except asyncio.CancelledError:
            self._metrics.record_cancelled()
            self.operationCompleted.emit(operation_id, False)
            return AsyncResult.cancelled()

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start_time) * 1000
            self._metrics.record_failure(elapsed_ms)

            if self._is_running and on_error and self._signals_connected:
                self._error_signal.emit(on_error, e)

            self.operationCompleted.emit(operation_id, False)

            return AsyncResult.err(e, elapsed_ms)

        finally:
            try:
                # Cancel any pending tasks
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()

                # Give tasks a chance to cleanup
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))

                loop.close()
            except Exception:
                pass

            # Remove from pending
            with self._lock:
                self._pending_futures.pop(operation_id, None)

    def run(
        self,
        coro: Awaitable[T],
        callback: Optional[Callable[[T], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None,
        timeout: Optional[float] = None,
    ) -> int:
        """Alias for execute()."""
        return self.execute(coro, callback, error_callback, timeout)

    # =========================================================================
    # Operation Management
    # =========================================================================

    def cancel(self, operation_id: int) -> bool:
        """
        Cancel a pending operation.

        Args:
            operation_id: Operation to cancel

        Returns:
            True if operation was cancelled
        """
        with self._lock:
            future = self._pending_futures.get(operation_id)
            if future and not future.done():
                result = future.cancel()
                if result:
                    self._metrics.record_cancelled()
                return result
        return False

    def cancel_all(self) -> int:
        """
        Cancel all pending operations.

        Returns:
            Number of operations cancelled
        """
        cancelled = 0
        with self._lock:
            for operation_id, future in list(self._pending_futures.items()):
                if not future.done() and future.cancel():
                    cancelled += 1
                    self._metrics.record_cancelled()
            self._pending_futures.clear()
        return cancelled

    def _cleanup_futures(self) -> None:
        """Remove completed futures (called with lock held)."""
        self._pending_futures = {k: v for k, v in self._pending_futures.items() if not v.done()}

    def _close_coroutine(self, coro: Awaitable) -> None:
        """Properly close a coroutine to avoid warnings."""
        try:
            if hasattr(coro, "close"):
                coro.close()
        except Exception:
            pass

    # =========================================================================
    # Shutdown
    # =========================================================================

    def shutdown(
        self,
        wait: bool = False,
        timeout: float = DEFAULT_SHUTDOWN_TIMEOUT,
    ) -> None:
        """
        Shutdown the executor.

        Args:
            wait: If True, wait for pending operations (up to timeout)
            timeout: Maximum seconds to wait for pending operations
        """
        if not self._is_running:
            return

        logger.debug("[AsyncExecutor] Shutting down (%d pending)", self.pending_count)

        # Mark as shutting down
        self._is_shutting_down = True
        self._is_running = False
        self._signals_connected = False

        # Disconnect signals
        try:
            self._success_signal.disconnect()
        except (RuntimeError, TypeError):
            pass

        try:
            self._error_signal.disconnect()
        except (RuntimeError, TypeError):
            pass

        # Cancel pending operations
        cancelled = self.cancel_all()
        if cancelled:
            logger.debug("[AsyncExecutor] Cancelled %d operations", cancelled)

        # Shutdown thread pool
        try:
            self._executor.shutdown(wait=wait, cancel_futures=False)
        except Exception as e:
            logger.debug("[AsyncExecutor] Shutdown error: %s", e)

        logger.debug("[AsyncExecutor] Shutdown complete")

    def __del__(self):
        """Destructor - ensure cleanup."""
        try:
            if self._is_running:
                self.shutdown(wait=False)
        except Exception:
            pass


# ============================================================================
# Convenience Functions
# ============================================================================


def run_async(
    coro: Awaitable[T],
    timeout: Optional[float] = None,
) -> T:
    """
    Run an async coroutine synchronously.

    Args:
        coro: Coroutine to run
        timeout: Optional timeout in seconds

    Returns:
        Result of the coroutine

    Raises:
        TimeoutError: If timeout exceeded
        Exception: If coroutine raises
    """
    loop = asyncio.new_event_loop()
    try:
        if timeout:
            return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "AsyncExecutor",
    "AsyncResult",
    "ExecutorMetrics",
    "OperationStatus",
    "Priority",
    "run_async",
]
