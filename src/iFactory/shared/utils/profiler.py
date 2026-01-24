"""
Performance profiling utilities for startup analysis.
ASCII-safe version for Windows compatibility.
"""

import time
import logging
import functools
from contextlib import contextmanager
from typing import Optional, List, Tuple, Callable, Any

logger = logging.getLogger(__name__)


@contextmanager
def profile_block(name: str, threshold_ms: float = 50.0):
    """
    Context manager to profile a code block.

    Args:
        name: Block name
        threshold_ms: Only log WARNING if exceeded (ms)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed_ms = (time.perf_counter() - start) * 1000
        if elapsed_ms >= threshold_ms:
            logger.warning(f"[SLOW] {name}: {elapsed_ms:.1f}ms")
        else:
            logger.debug(f"[PROFILE] {name}: {elapsed_ms:.1f}ms")


def profile_method(threshold_ms: float = 50.0):
    """Decorator to profile method execution time."""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if elapsed_ms >= threshold_ms:
                    logger.warning(f"[SLOW] {func.__module__}.{func.__qualname__}: {elapsed_ms:.1f}ms")

        return wrapper

    return decorator


def profile_async_method(threshold_ms: float = 50.0):
    """Decorator to profile async method."""

    def decorator(func: Callable) -> Callable:

        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed_ms = (time.perf_counter() - start) * 1000
                if elapsed_ms >= threshold_ms:
                    logger.warning(f"[SLOW ASYNC] {func.__module__}.{func.__qualname__}: {elapsed_ms:.1f}ms")

        return wrapper

    return decorator


class StartupProfiler:
    """
    Track startup timing across multiple phases.
    ASCII-safe for Windows compatibility.
    """

    _instance: Optional["StartupProfiler"] = None

    def __new__(cls) -> "StartupProfiler":
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize profiler (only once due to singleton)."""
        if self._initialized:
            return
        self._start_time = time.perf_counter()
        self._checkpoints: List[Tuple[str, float, float]] = []
        self._initialized = True

    def reset(self) -> None:
        """Reset profiler for new run."""
        self._start_time = time.perf_counter()
        self._checkpoints.clear()

    def checkpoint(self, name: str) -> float:
        """
        Record a checkpoint.

        Args:
            name: Checkpoint name

        Returns:
            Elapsed time in seconds since start
        """
        now = time.perf_counter()
        elapsed = now - self._start_time
        prev_elapsed = self._checkpoints[-1][1] if self._checkpoints else 0
        delta = elapsed - prev_elapsed
        self._checkpoints.append((name, elapsed, delta))
        logger.info(f"[STARTUP] {name}: +{elapsed * 1000:.0f}ms total (delta {delta * 1000:.0f}ms)")
        return elapsed

    def get_elapsed(self) -> float:
        """Get elapsed time since start in seconds."""
        return time.perf_counter() - self._start_time

    def report(self) -> None:
        """Print final startup report."""
        if not self._checkpoints:
            logger.info("[STARTUP REPORT] No checkpoints recorded")
            return
        logger.info("")
        logger.info("=" * 70)
        logger.info("[STARTUP REPORT]")
        logger.info("-" * 70)
        max_name_len = max((len(cp[0]) for cp in self._checkpoints))
        for name, elapsed, delta in self._checkpoints:
            bar_len = int(delta * 10)
            bar = "#" * min(bar_len, 50)
            if delta > 1.0:
                level = "[CRITICAL]"
            elif delta > 0.5:
                level = "[SLOW]    "
            elif delta > 0.1:
                level = "[WARN]    "
            else:
                level = "[OK]      "
            logger.info(f"  {level} {name:<{max_name_len}s}  {delta * 1000:6.0f}ms  {bar}")
        total = self._checkpoints[-1][1] if self._checkpoints else 0
        logger.info("-" * 70)
        logger.info(f"  {'TOTAL':<{max_name_len + 12}s}  {total * 1000:6.0f}ms")
        logger.info("=" * 70)
        logger.info("")

    def get_slow_phases(self, threshold_ms: float = 500.0) -> List[Tuple[str, float]]:
        """
        Get phases that exceeded threshold.

        Args:
            threshold_ms: Threshold in milliseconds

        Returns:
            List of (name, delta_seconds) tuples
        """
        threshold_s = threshold_ms / 1000.0
        return [(name, delta) for (name, _, delta) in self._checkpoints if delta > threshold_s]


startup_profiler = StartupProfiler()
__all__ = ["profile_block", "profile_method", "profile_async_method", "StartupProfiler", "startup_profiler"]
