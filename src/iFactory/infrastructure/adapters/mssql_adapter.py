# src/iFactory/infrastructure/adapters/mssql_adapter.py
"""
MSSQL Adapter - Production-ready with resilience patterns.
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Final
from datetime import datetime, timedelta
from enum import Enum, auto
from typing import (
    Any,
    Callable,
    Dict,
    Final,
    Generic,
    List,
    Optional,
    Set,
    Tuple,
    TypeVar,
)

from sqlalchemy import bindparam, event, text
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncConnection, create_async_engine
from sqlalchemy.pool import NullPool, AsyncAdaptedQueuePool

from iFactory.application.ports.remote import IRemoteDataSource
from iFactory.infrastructure.configuration.db_settings import DatabaseConfig

logger = logging.getLogger(__name__)

T = TypeVar("T")

# ============================================================================
# Constants
# ============================================================================

DEFAULT_QUERY_TIMEOUT: Final[float] = 30.0
DEFAULT_MATERIAL_TIMEOUT: Final[float] = 5.0
DEFAULT_MATERIAL_COOLDOWN: Final[float] = 30.0
DEFAULT_CACHE_TTL: Final[float] = 60.0
MAX_BATCH_SIZE: Final[int] = 50
HEALTH_CHECK_INTERVAL: Final[float] = 60.0


# ============================================================================
# Circuit Breaker Implementation (Enhanced)
# ============================================================================


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = auto()  # Normal operation
    OPEN = auto()  # Failing, reject requests
    HALF_OPEN = auto()  # Testing recovery


@dataclass
class CircuitBreakerMetrics:
    """Metrics for circuit breaker monitoring."""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_changes: int = 0

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls

    @property
    def failure_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.failed_calls / self.total_calls

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "failed_calls": self.failed_calls,
            "rejected_calls": self.rejected_calls,
            "success_rate": f"{self.success_rate:.1%}",
            "failure_rate": f"{self.failure_rate:.1%}",
            "state_changes": self.state_changes,
        }


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""

    failure_threshold: int = 5
    success_threshold: int = 3  # Successes needed in half-open to close
    recovery_timeout: float = 30.0
    half_open_max_calls: int = 3
    failure_rate_threshold: float = 0.5  # 50% failure rate triggers open
    min_calls_for_rate: int = 10  # Minimum calls before rate check


class CircuitBreaker:
    """
    Enhanced circuit breaker with rate-based triggering.

    Features:
    - Failure count and rate-based triggering
    - Metrics collection
    - Thread-safe state management
    - Configurable thresholds
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self._config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._half_open_successes = 0
        self._last_failure_time: Optional[datetime] = None
        self._last_state_change: datetime = datetime.now()
        self._lock = asyncio.Lock()
        self._metrics = CircuitBreakerMetrics()

        # Sliding window for rate calculation
        self._recent_results: List[Tuple[datetime, bool]] = []
        self._window_size = timedelta(seconds=60)

    @property
    def state(self) -> CircuitState:
        return self._state

    @property
    def metrics(self) -> CircuitBreakerMetrics:
        return self._metrics

    @property
    def is_available(self) -> bool:
        """Check if circuit allows requests."""
        if self._state == CircuitState.CLOSED:
            return True
        if self._state == CircuitState.OPEN:
            return self._should_attempt_recovery()
        # HALF_OPEN
        return self._half_open_calls < self._config.half_open_max_calls

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if not self._last_failure_time:
            return True
        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self._config.recovery_timeout

    def _clean_sliding_window(self) -> None:
        """Remove old entries from sliding window."""
        cutoff = datetime.now() - self._window_size
        self._recent_results = [(ts, success) for ts, success in self._recent_results if ts > cutoff]

    def _calculate_failure_rate(self) -> float:
        """Calculate failure rate from sliding window."""
        self._clean_sliding_window()
        if len(self._recent_results) < self._config.min_calls_for_rate:
            return 0.0
        failures = sum(1 for _, success in self._recent_results if not success)
        return failures / len(self._recent_results)

    async def record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.successful_calls += 1
            self._metrics.last_success_time = datetime.now()
            self._recent_results.append((datetime.now(), True))

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_successes += 1
                if self._half_open_successes >= self._config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
            elif self._state == CircuitState.CLOSED:
                self._failure_count = max(0, self._failure_count - 1)

    async def record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self._metrics.total_calls += 1
            self._metrics.failed_calls += 1
            self._metrics.last_failure_time = datetime.now()
            self._last_failure_time = datetime.now()
            self._failure_count += 1
            self._recent_results.append((datetime.now(), False))

            if self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.CLOSED:
                should_open = (
                    self._failure_count >= self._config.failure_threshold or self._calculate_failure_rate() >= self._config.failure_rate_threshold
                )
                if should_open:
                    self._transition_to(CircuitState.OPEN)

    async def try_acquire(self) -> bool:
        """Try to acquire permission for a call."""
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to(CircuitState.HALF_OPEN)
                    self._half_open_calls = 1
                    return True
                self._metrics.rejected_calls += 1
                return False

            # HALF_OPEN
            if self._half_open_calls < self._config.half_open_max_calls:
                self._half_open_calls += 1
                return True

            self._metrics.rejected_calls += 1
            return False

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = datetime.now()
        self._metrics.state_changes += 1

        if new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._half_open_calls = 0
            self._half_open_successes = 0
            logger.info("[CircuitBreaker] CLOSED - Circuit recovered")
        elif new_state == CircuitState.OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0
            logger.warning("[CircuitBreaker] OPEN - Circuit tripped after %d failures", self._failure_count)
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
            self._half_open_successes = 0
            logger.info("[CircuitBreaker] HALF_OPEN - Testing recovery")

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0
        self._half_open_successes = 0
        self._last_failure_time = None
        self._recent_results.clear()
        logger.info("[CircuitBreaker] Reset to CLOSED")


# ============================================================================
# Retry Configuration (Enhanced)
# ============================================================================


@dataclass
class RetryConfig:
    """Configuration for retry logic."""

    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0
    jitter: bool = True  # Add random jitter to prevent thundering herd
    retryable_exceptions: Tuple[type, ...] = (
        OperationalError,
        ConnectionError,
        TimeoutError,
        asyncio.TimeoutError,
    )


async def retry_with_backoff(
    func: Callable[[], T],
    config: RetryConfig,
    operation_name: str = "operation",
) -> T:
    """
    Execute function with exponential backoff retry.

    Args:
        func: Async callable to execute
        config: Retry configuration
        operation_name: Name for logging

    Returns:
        Result of successful function call

    Raises:
        Last exception if all retries fail
    """
    import random

    last_exception: Optional[Exception] = None

    for attempt in range(1, config.max_attempts + 1):
        try:
            return await func()
        except config.retryable_exceptions as e:
            last_exception = e

            if attempt == config.max_attempts:
                logger.error("[Retry] %s failed after %d attempts: %s", operation_name, attempt, e)
                raise

            # Calculate delay with exponential backoff
            delay = min(
                config.base_delay * (config.exponential_base ** (attempt - 1)),
                config.max_delay,
            )

            # Add jitter (±25%)
            if config.jitter:
                jitter = delay * 0.25 * (random.random() * 2 - 1)
                delay = max(0.1, delay + jitter)

            logger.warning("[Retry] %s attempt %d/%d failed: %s. Retrying in %.1fs...", operation_name, attempt, config.max_attempts, e, delay)
            await asyncio.sleep(delay)

    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError(f"{operation_name} failed without exception")


# ============================================================================
# Query Cache
# ============================================================================


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with TTL."""

    value: T
    created_at: datetime
    ttl: float
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl

    def touch(self) -> None:
        self.hits += 1


class QueryCache:
    """
    Simple in-memory cache with TTL and size limits.

    Features:
    - Per-key TTL
    - Max size with LRU eviction
    - Hit/miss statistics
    """

    def __init__(self, max_size: int = 1000, default_ttl: float = DEFAULT_CACHE_TTL):
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None

            entry.touch()
            self._hits += 1
            return entry.value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Set value in cache."""
        async with self._lock:
            # Evict if at capacity
            if len(self._cache) >= self._max_size:
                self._evict_lru()

            self._cache[key] = CacheEntry(
                value=value,
                created_at=datetime.now(),
                ttl=ttl or self._default_ttl,
            )

    async def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def invalidate_prefix(self, prefix: str) -> int:
        """Invalidate all entries with key prefix."""
        async with self._lock:
            keys_to_remove = [k for k in self._cache if k.startswith(prefix)]
            for key in keys_to_remove:
                del self._cache[key]
            return len(keys_to_remove)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()

    def _evict_lru(self) -> None:
        """Evict least recently used entries."""
        if not self._cache:
            return

        # Sort by hits (ascending) and created_at (ascending)
        sorted_keys = sorted(self._cache.keys(), key=lambda k: (self._cache[k].hits, self._cache[k].created_at))

        # Remove 10% of entries
        remove_count = max(1, len(self._cache) // 10)
        for key in sorted_keys[:remove_count]:
            del self._cache[key]

    @property
    def stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        hit_rate = self._hits / total if total > 0 else 0.0
        return {
            "size": len(self._cache),
            "max_size": self._max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{hit_rate:.1%}",
        }


# ============================================================================
# Material Input Data Class
# ============================================================================


@dataclass(frozen=True, slots=True)
class MaterialInputRecord:
    """Immutable material input record."""

    lot_no: str
    material_batch: str
    material_name: str
    feed_time: datetime
    feed_qty: float = 0.0
    feed_user: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lot_no": self.lot_no,
            "material_batch": self.material_batch,
            "material_name": self.material_name,
            "feed_time": self.feed_time.isoformat() if self.feed_time else None,
            "feed_qty": self.feed_qty,
            "feed_user": self.feed_user,
        }


# ============================================================================
# Cooldown Manager
# ============================================================================


class CooldownManager:
    """
    Manages cooldown periods for failed operations.

    Implements progressive cooldown: each failure increases cooldown duration.
    """

    def __init__(
        self,
        base_cooldown: float = 60.0,
        max_cooldown: float = 300.0,
        cooldown_multiplier: float = 2.0,
    ):
        self._base_cooldown = base_cooldown
        self._max_cooldown = max_cooldown
        self._multiplier = cooldown_multiplier
        self._cooldowns: Dict[str, Tuple[datetime, float, int]] = {}
        self._lock = asyncio.Lock()

    async def is_on_cooldown(self, key: str) -> bool:
        """Check if key is currently on cooldown."""
        async with self._lock:
            if key not in self._cooldowns:
                return False

            start_time, duration, _ = self._cooldowns[key]
            elapsed = (datetime.now() - start_time).total_seconds()

            if elapsed >= duration:
                # Cooldown expired - keep failure count for progressive cooldown
                return False

            return True

    async def start_cooldown(self, key: str) -> float:
        """Start or extend cooldown for a key. Returns cooldown duration."""
        async with self._lock:
            failure_count = 1

            if key in self._cooldowns:
                _, _, failure_count = self._cooldowns[key]
                failure_count += 1

            # Progressive cooldown
            duration = min(
                self._base_cooldown * (self._multiplier ** (failure_count - 1)),
                self._max_cooldown,
            )

            self._cooldowns[key] = (datetime.now(), duration, failure_count)

            logger.debug("[Cooldown] %s: %.1fs (failure #%d)", key, duration, failure_count)

            return duration

    async def clear_cooldown(self, key: str) -> None:
        """Clear cooldown for a key (on success)."""
        async with self._lock:
            self._cooldowns.pop(key, None)

    async def clear_all(self) -> None:
        """Clear all cooldowns."""
        async with self._lock:
            self._cooldowns.clear()

    async def get_remaining(self, key: str) -> float:
        """Get remaining cooldown time in seconds."""
        async with self._lock:
            if key not in self._cooldowns:
                return 0.0

            start_time, duration, _ = self._cooldowns[key]
            elapsed = (datetime.now() - start_time).total_seconds()
            return max(0.0, duration - elapsed)


# ============================================================================
# Connection Health Monitor
# ============================================================================


class ConnectionHealthMonitor:
    """
    Monitors database connection health.

    Features:
    - Periodic health checks
    - Connection latency tracking
    - Automatic reconnection triggers
    """

    def __init__(
        self,
        check_interval: float = HEALTH_CHECK_INTERVAL,
        latency_threshold_ms: float = 1000.0,
    ):
        self._check_interval = check_interval
        self._latency_threshold = latency_threshold_ms
        self._is_healthy = True
        self._last_check: Optional[datetime] = None
        self._last_latency_ms: float = 0.0
        self._consecutive_failures = 0
        self._check_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable[[bool], None]] = []

    @property
    def is_healthy(self) -> bool:
        return self._is_healthy

    @property
    def last_latency_ms(self) -> float:
        return self._last_latency_ms

    def add_health_callback(self, callback: Callable[[bool], None]) -> None:
        """Add callback to be notified of health changes."""
        self._callbacks.append(callback)

    async def check_health(self, check_func: Callable[[], bool]) -> bool:
        """Perform a health check."""
        start = datetime.now()

        try:
            result = await check_func()
            self._last_latency_ms = (datetime.now() - start).total_seconds() * 1000
            self._last_check = datetime.now()

            if result:
                self._consecutive_failures = 0
                if not self._is_healthy:
                    self._is_healthy = True
                    self._notify_health_change(True)
            else:
                self._consecutive_failures += 1
                if self._is_healthy and self._consecutive_failures >= 3:
                    self._is_healthy = False
                    self._notify_health_change(False)

            return result

        except Exception as e:
            self._consecutive_failures += 1
            self._last_latency_ms = -1

            if self._is_healthy and self._consecutive_failures >= 3:
                self._is_healthy = False
                self._notify_health_change(False)

            logger.debug("[HealthMonitor] Check failed: %s", e)
            return False

    def _notify_health_change(self, is_healthy: bool) -> None:
        """Notify callbacks of health change."""
        for callback in self._callbacks:
            try:
                callback(is_healthy)
            except Exception as e:
                logger.debug("[HealthMonitor] Callback error: %s", e)

    def get_status(self) -> Dict[str, Any]:
        """Get health status summary."""
        return {
            "is_healthy": self._is_healthy,
            "last_check": self._last_check.isoformat() if self._last_check else None,
            "last_latency_ms": self._last_latency_ms,
            "consecutive_failures": self._consecutive_failures,
        }


# ============================================================================
# MSSQL Adapter Configuration
# ============================================================================


@dataclass
class MssqlAdapterConfig:
    """Configuration for MSSQL adapter - COMPLETE VERSION."""

    # Timeouts
    query_timeout: float = DEFAULT_QUERY_TIMEOUT
    connect_timeout: int = 5
    material_timeout: float = DEFAULT_MATERIAL_TIMEOUT

    # Cooldown
    material_cooldown: float = DEFAULT_MATERIAL_COOLDOWN
    max_cooldown: float = 120.0

    # Retry configuration
    retry: RetryConfig = field(default_factory=RetryConfig)

    # Circuit breaker configuration
    circuit_breaker: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)

    # Cache configuration
    cache_enabled: bool = True
    cache_ttl: float = DEFAULT_CACHE_TTL
    cache_max_size: int = 500

    # Health check configuration
    health_check_interval: float = HEALTH_CHECK_INTERVAL
    health_check_enabled: bool = True

    # Performance monitoring
    slow_query_threshold_ms: float = 1000.0
    very_slow_query_threshold_ms: float = 3000.0

    # Batch operations
    max_batch_size: int = MAX_BATCH_SIZE

    # Connection pooling (NullPool by default)
    pool_size: int = 0
    max_overflow: int = 0
    pool_recycle: int = -1
    pool_pre_ping: bool = False


# ============================================================================
# MSSQL Adapter Implementation (FIXED)
# ============================================================================


class MssqlAdapter(IRemoteDataSource):
    """
    Production-ready MSSQL adapter with resilience patterns.

    Features:
    - Circuit breaker for failure isolation
    - Retry with exponential backoff
    - Query result caching
    - Progressive cooldown for failing devices
    - Connection health monitoring
    - Detailed metrics and observability
    - Graceful shutdown handling

    Usage:
        adapter = MssqlAdapter(connection_string)

        # Fetch latest status for devices
        records = await adapter.fetch_latest_status(["DEV01", "DEV02"])

        # Fetch material inputs
        materials = await adapter.fetch_material_inputs("DEV01")

        # Check health
        is_healthy = await adapter.health_check()

        # Cleanup
        await adapter.dispose()
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        config: Optional[MssqlAdapterConfig] = None,
    ) -> None:
        self._config = config or MssqlAdapterConfig()
        self._engine: Optional[AsyncEngine] = None
        self._connection_string = connection_string

        # State flags
        self._is_disposed = False
        self._disposing = False
        self._is_initialized = False

        # Concurrency control
        self._active_count = 0
        self._lock = asyncio.Lock()
        self._operation_semaphore = asyncio.Semaphore(20)  # Max concurrent operations

        # Task registry for cancellation
        self._active_tasks: Set[asyncio.Task] = set()
        self._task_lock = asyncio.Lock()

        # Resilience components
        self._circuit_breaker = CircuitBreaker(self._config.circuit_breaker)
        self._cooldown_manager = CooldownManager(
            base_cooldown=self._config.material_cooldown,
            max_cooldown=self._config.max_cooldown,
        )
        self._health_monitor = ConnectionHealthMonitor(
            check_interval=self._config.health_check_interval,
        )

        # Cache
        self._cache: Optional[QueryCache] = None
        if self._config.cache_enabled:
            self._cache = QueryCache(
                max_size=self._config.cache_max_size,
                default_ttl=self._config.cache_ttl,
            )

        # Metrics
        self._metrics = _AdapterMetrics()

        # Initialize engine
        if connection_string:
            self._create_engine(connection_string)
        else:
            db_config = DatabaseConfig()
            if db_config.mssql_url:
                self._create_engine(db_config.mssql_url)
                logger.info(
                    "[MssqlAdapter] Using config: host=%s, db=%s",
                    db_config.mssql_host,
                    db_config.mssql_db,
                )

    def _create_engine(self, url: str) -> None:
        """Create SQLAlchemy async engine."""
        from sqlalchemy.pool import NullPool

        self._engine = create_async_engine(
            url,
            poolclass=NullPool,
            echo=False,
            connect_args={
                "timeout": self._config.connect_timeout,
            },
        )

        self._is_initialized = True
        logger.info(
            "[MssqlAdapter] Engine created with NullPool " "(timeout=%ds, material_timeout=%.1fs)",
            self._config.query_timeout,
            self._config.material_timeout,
        )

    # Helper to register tasks
    def _register_task(self, task: asyncio.Task) -> None:
        """Register an active task for cancellation tracking."""
        self._active_tasks.add(task)
        task.add_done_callback(self._active_tasks.discard)

    # =========================================================================
    # Properties
    # =========================================================================

    @property
    def is_available(self) -> bool:
        """Check if adapter is available for operations."""
        return not self._is_disposed and not self._disposing and self._engine is not None and self._circuit_breaker.is_available

    @property
    def circuit_state(self) -> CircuitState:
        """Current circuit breaker state."""
        return self._circuit_breaker.state

    @property
    def is_healthy(self) -> bool:
        """Check if connection is healthy."""
        return self._health_monitor.is_healthy

    @property
    def metrics(self) -> Dict[str, Any]:
        """Get adapter metrics."""
        return {
            "circuit_breaker": self._circuit_breaker.metrics.to_dict(),
            "health": self._health_monitor.get_status(),
            "cache": self._cache.stats if self._cache else None,
            "operations": self._metrics.to_dict(),
            "active_tasks": len(self._active_tasks),
        }

    # =========================================================================
    # Operation Lifecycle
    # =========================================================================

    async def _enter_operation(self) -> bool:
        """Enter an operation with circuit breaker check."""
        if self._disposing or self._is_disposed:
            return False

        if not await self._circuit_breaker.try_acquire():
            self._metrics.record_rejected()
            return False

        async with self._lock:
            self._active_count += 1

        return True

    async def _exit_operation(self, success: bool = True) -> None:
        """Exit an operation and record result."""
        if success:
            await self._circuit_breaker.record_success()
            self._metrics.record_success()
        else:
            await self._circuit_breaker.record_failure()
            self._metrics.record_failure()

        async with self._lock:
            self._active_count = max(0, self._active_count - 1)

    @asynccontextmanager
    async def _operation_context(self, operation_name: str = "operation"):
        """Context manager for database operations."""
        if not await self._enter_operation():
            raise ConnectionError(f"Adapter not available for {operation_name}")

        success = False
        start_time = datetime.now()

        try:
            yield
            success = True
        finally:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
            await self._exit_operation(success)

            if elapsed_ms > 1000:
                logger.debug("[MssqlAdapter] %s took %.0fms", operation_name, elapsed_ms)

    async def _execute_with_timeout(
        self,
        coro,
        timeout: Optional[float] = None,
        operation_name: str = "query",
        is_retry: bool = False,
    ):
        """Execute coroutine with timeout and performance logging - ENHANCED."""

        # ========== ADAPTIVE TIMEOUT FOR RETRIES ==========
        if is_retry and timeout:
            timeout = min(timeout * 0.6, 3.0)
            logger.debug(f"[MssqlAdapter] Retry with reduced timeout: {timeout:.1f}s")

        timeout = timeout or self._config.query_timeout

        # Task tracking
        current_task = asyncio.current_task()
        if current_task:
            async with self._task_lock:
                if not self._disposing:
                    self._active_tasks.add(current_task)

        start_time = datetime.now()

        try:
            result = await asyncio.wait_for(coro, timeout=timeout)

            # ========== ENHANCED PERFORMANCE LOGGING ==========
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            # Very slow query warning
            if elapsed_ms > self._config.very_slow_query_threshold_ms:
                logger.warning(
                    f"[SLOW QUERY] {operation_name}: {elapsed_ms:.0f}ms " f"(threshold: {self._config.very_slow_query_threshold_ms:.0f}ms)"
                )
                # Record for metrics
                self._metrics.record_slow_query(operation_name, elapsed_ms)

            # Slow query info
            elif elapsed_ms > self._config.slow_query_threshold_ms:
                logger.info(f"[Slow] {operation_name}: {elapsed_ms:.0f}ms")

            # Debug fast queries (optional)
            elif elapsed_ms < 100:
                logger.debug(f"[Fast] {operation_name}: {elapsed_ms:.0f}ms")
            # ==================================================

            return result

        except asyncio.TimeoutError:
            elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000

            # ========== DETAILED TIMEOUT LOGGING ==========
            logger.error(f"[TIMEOUT] {operation_name} exceeded {timeout:.1f}s limit " f"(actual: {elapsed_ms:.0f}ms)")

            # Record timeout metrics
            self._metrics.record_timeout(operation_name, elapsed_ms)

            # Suggest optimization
            if "material" in operation_name.lower():
                logger.info(f"[Hint] Consider reducing date range for material queries " f"or contact DBA to optimize RPT_FEEDING_DETAIL table")
            # ===============================================

            raise TimeoutError(f"{operation_name} timed out after {timeout}s")

        except asyncio.CancelledError:
            if not self._disposing:
                elapsed_ms = (datetime.now() - start_time).total_seconds() * 1000
                logger.debug(f"[Cancelled] {operation_name} after {elapsed_ms:.0f}ms")
            raise

        finally:
            # Cleanup task tracking
            if current_task:
                async with self._task_lock:
                    self._active_tasks.discard(current_task)

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def _is_event_loop_usable(self) -> bool:
        """
        Check if we have a usable event loop.

        Returns False if:
        - No event loop exists
        - Event loop is closed
        - We're in disposal
        """
        if self._disposing or self._is_disposed:
            return False

        try:
            loop = asyncio.get_running_loop()
            return not loop.is_closed()
        except RuntimeError:
            return False

    def _parse_datetime(self, val: Any) -> datetime:
        """Parse datetime from various formats."""
        if isinstance(val, datetime):
            return val
        if isinstance(val, str):
            try:
                clean_val = val[:23] if len(val) > 23 else val
                return datetime.strptime(clean_val, "%Y-%m-%d %H:%M:%S.%f")
            except ValueError:
                try:
                    return datetime.strptime(val.split(".")[0], "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return datetime.now()
        return datetime.now()

    def _map_status_row(self, row: Any) -> Dict[str, Any]:
        """Map a database row to status dictionary."""
        equip_code = str(row[0]).strip() if row[0] else "UNKNOWN"
        equip_status = str(row[1]) if row[1] else "0"
        start_time = self._parse_datetime(row[2])
        end_time_val = row[3]
        reason_code = str(row[4]).strip() if row[4] else None
        equip_name = str(row[5]).strip() if row[5] else None
        last_update = self._parse_datetime(end_time_val) if end_time_val else datetime.now()

        return {
            "equip_code": equip_code,
            "equip_status": equip_status,
            "raw_status": equip_status,
            "start_time": start_time,
            "end_time": self._parse_datetime(end_time_val) if end_time_val else None,
            "reason_code": reason_code,
            "equip_name": equip_name,
            "last_update": last_update,
        }

    # =========================================================================
    # Fetch Latest Status
    # =========================================================================

    async def fetch_latest_status(
        self,
        equipment_codes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Fetch latest status for equipment codes.

        Args:
            equipment_codes: List of equipment codes to fetch.
                        If None, fetches all equipment.

        Returns:
            List of status dictionaries.
        """
        if not self._is_event_loop_usable():
            logger.debug("[MssqlAdapter] Event loop not available for fetch_latest_status")
            return []

        if not self.is_available:
            return []

        if equipment_codes is not None and len(equipment_codes) == 0:
            return []

        # Check cache for single device
        if equipment_codes and len(equipment_codes) == 1 and self._cache:
            cache_key = f"status:{equipment_codes[0]}"
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        async with self._operation_semaphore:
            try:
                async with self._operation_context("fetch_latest_status"):
                    result = await self._do_fetch_latest_status(equipment_codes)

                    # Cache result for single device
                    if equipment_codes and len(equipment_codes) == 1 and self._cache and result:
                        cache_key = f"status:{equipment_codes[0]}"
                        await self._cache.set(cache_key, result, ttl=10.0)

                    return result

            except (TimeoutError, OperationalError, ConnectionError) as e:
                if not self._is_disposed and not self._disposing:
                    logger.error("[MssqlAdapter] Fetch latest status error: %s", e)
                return []
            except asyncio.CancelledError:
                if not self._disposing:
                    raise
                return []
            except Exception as e:
                error_msg = str(e)

                if "Event loop is closed" in error_msg or "closed" in error_msg.lower():
                    logger.debug("[MssqlAdapter] Event loop closed during fetch_latest_status")
                    return []

                if not self._is_disposed and not self._disposing:
                    logger.error("[MssqlAdapter] Unexpected error: %s", error_msg[:200])  # Truncate long errors
                return []

    async def _do_fetch_latest_status(
        self,
        equipment_codes: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Execute the fetch latest status query - FIXED VERSION."""
        if not self._engine or self._disposing:
            return []

        if equipment_codes:
            # SQL injection protection
            safe_codes = [code.replace("'", "''") for code in equipment_codes]
            codes_list = "'" + "','".join(safe_codes) + "'"
            where_clause = f"WHERE E.EQUIP_CODE IN ({codes_list})"
        else:
            where_clause = ""

        # ========== FIXED: Use OUTER APPLY for devices without status ==========
        raw_sql = f"""
        SELECT 
            E.EQUIP_CODE,
            ISNULL(latest.EQUIP_STATUS, '0') as EQUIP_STATUS,
            latest.START_TIME,
            latest.END_TIME,
            latest.REASON_CODE,
            E.EQUIP_NAME
        FROM yntti.dbo.TT_EQ_EQUIPMENT E WITH (NOLOCK)
        OUTER APPLY (  -- Changed from CROSS APPLY to include devices without status
            SELECT TOP 1
                S.EQUIP_STATUS,
                S.START_TIME,
                S.END_TIME,
                S.REASON_CODE
            FROM yntti.dbo.TT_EQ_STATUS S WITH (NOLOCK)
            WHERE S.EQUIP_CODE = E.EQUIP_CODE
            AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
            ORDER BY S.START_TIME DESC
        ) latest
        {where_clause}
        """
        # ========================================================================

        try:
            async with self._engine.connect() as conn:
                if self._disposing:
                    return []

                result = await conn.execute(text(raw_sql))
                rows = result.fetchall()

                # Enhanced logging
                if equipment_codes:
                    logger.info(f"[MssqlAdapter] Query executed: " f"requested={len(equipment_codes)}, " f"returned={len(rows)}")

                    # Check for missing devices
                    returned_codes = {str(row[0]).strip().upper() for row in rows if row[0]}
                    requested_codes = {code.upper() for code in equipment_codes}
                    missing_codes = requested_codes - returned_codes

                    if missing_codes:
                        logger.warning(f"[MssqlAdapter] Missing devices not in TT_EQ_EQUIPMENT: " f"{sorted(missing_codes)}")

                # Process results with better null handling
                results = []
                for row in rows:
                    try:
                        mapped = self._map_status_row_enhanced(row)
                        results.append(mapped)
                    except Exception as e:
                        logger.debug(f"[MssqlAdapter] Row mapping error: {e}")
                        continue

                return results

        except Exception as e:
            logger.error(f"[MssqlAdapter] Query execution failed: {e}")
            return []

    def _map_status_row_enhanced(self, row: Any) -> Dict[str, Any]:
        """Enhanced row mapping with null handling."""
        equip_code = str(row[0]).strip() if row[0] else "UNKNOWN"

        # Handle devices without status records
        if row[1] is None and row[2] is None:
            # Device exists but no status records
            return {
                "equip_code": equip_code,
                "equip_status": "0",  # Default to STOP
                "raw_status": "NO_DATA",
                "start_time": datetime.now(),
                "end_time": None,
                "reason_code": "NO_STATUS_RECORDS",
                "equip_name": str(row[5]).strip() if row[5] else None,
                "last_update": datetime.now(),
                "has_data": False,  # Flag for UI
            }

        # Normal mapping for devices with status
        equip_status = str(row[1]) if row[1] else "0"
        start_time = self._parse_datetime(row[2]) if row[2] else datetime.now()
        end_time = self._parse_datetime(row[3]) if row[3] else None
        reason_code = str(row[4]).strip() if row[4] else None
        equip_name = str(row[5]).strip() if row[5] else None

        return {
            "equip_code": equip_code,
            "equip_status": equip_status,
            "raw_status": equip_status,
            "start_time": start_time,
            "end_time": end_time,
            "reason_code": reason_code,
            "equip_name": equip_name,
            "last_update": end_time or datetime.now(),
            "has_data": True,
        }

    # =========================================================================
    # Fetch Device History
    # =========================================================================

    async def fetch_device_status(
        self,
        equip_code: str,
        days: int = 1,
    ) -> List[Dict[str, Any]]:
        """Fetch device status history for specified days."""
        if not self.is_available:
            return []

        now = datetime.now()
        start_of_range = now - timedelta(days=days)
        return await self.fetch_device_history_range(equip_code, start_of_range, now)

    async def fetch_device_history_range(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch device status history for a time range."""
        if not self._is_event_loop_usable():
            logger.debug("[MssqlAdapter] Event loop not available for fetch_device_history_range")
            return []

        if not self.is_available:
            return []

        # Check cache
        cache_key = f"history:{equip_code}:{start_time.date()}:{end_time.date()}"
        if self._cache:
            cached = await self._cache.get(cache_key)
            if cached is not None:
                return cached

        async with self._operation_semaphore:
            try:
                async with self._operation_context(f"fetch_history({equip_code})"):
                    result = await self._do_fetch_history_range(equip_code, start_time, end_time)

                    # Cache if successful
                    if self._cache and result:
                        await self._cache.set(cache_key, result, ttl=60.0)

                    return result

            except (TimeoutError, OperationalError, ConnectionError) as e:
                if not self._is_disposed:
                    logger.error("[MssqlAdapter] History fetch error for %s: %s", equip_code, e)
                return []
            except asyncio.CancelledError:
                if not self._disposing:
                    raise
                return []
            except Exception as e:
                if not self._is_disposed:
                    logger.error("[MssqlAdapter] Unexpected history error: %s", e)
                return []

    async def _do_fetch_history_range(
        self,
        equip_code: str,
        start_time: datetime,
        end_time: datetime,
    ) -> List[Dict[str, Any]]:
        """Execute history range query."""
        if not self._engine or self._disposing:
            return []

        query = """
        SELECT 
            S.EQUIP_CODE, S.EQUIP_STATUS, S.START_TIME, S.END_TIME, S.REASON_CODE,
            E.EQUIP_NAME
        FROM TT_EQ_STATUS S WITH (NOLOCK)
        LEFT JOIN TT_EQ_EQUIPMENT E WITH (NOLOCK) ON S.EQUIP_CODE = E.EQUIP_CODE
        WHERE S.EQUIP_CODE = :code 
            AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
            AND S.START_TIME <= :end_time
            AND (S.END_TIME >= :start_time OR S.END_TIME IS NULL)
        ORDER BY S.START_TIME ASC
        """

        async with self._engine.connect() as conn:
            if self._disposing:
                return []

            result = await conn.execute(
                text(query),
                {
                    "code": equip_code,
                    "start_time": start_time,
                    "end_time": end_time,
                },
            )
            rows = result.fetchall()
            return [self._map_status_row(row) for row in rows]

    async def fetch_latest_history_records(
        self,
        equip_code: str,
        limit: int = 1,
    ) -> List[Dict[str, Any]]:
        """Fetch most recent history records for a device."""
        if not self._is_event_loop_usable():
            logger.debug("[MssqlAdapter] Event loop not available for fetch_latest_history_records")
            return []

        if not self.is_available:
            return []

        async with self._operation_semaphore:
            try:
                async with self._operation_context(f"fetch_latest({equip_code})"):
                    return await self._do_fetch_latest_records(equip_code, limit)

            except (TimeoutError, OperationalError, ConnectionError) as e:
                if not self._is_disposed:
                    logger.error("[MssqlAdapter] Latest history error for %s: %s", equip_code, e)
                return []
            except asyncio.CancelledError:
                if not self._disposing:
                    raise
                return []
            except Exception as e:
                if not self._is_disposed:
                    logger.error("[MssqlAdapter] Unexpected latest error: %s", e)
                return []

    async def _do_fetch_latest_records(
        self,
        equip_code: str,
        limit: int,
    ) -> List[Dict[str, Any]]:
        """Execute latest records query."""
        if not self._engine or self._disposing:
            return []

        query = """
        SELECT TOP(:limit)
            S.EQUIP_CODE, S.EQUIP_STATUS, S.START_TIME, S.END_TIME, S.REASON_CODE,
            E.EQUIP_NAME
        FROM TT_EQ_STATUS S WITH (NOLOCK)
        LEFT JOIN TT_EQ_EQUIPMENT E WITH (NOLOCK) ON S.EQUIP_CODE = E.EQUIP_CODE
        WHERE S.EQUIP_CODE = :code 
            AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
        ORDER BY S.START_TIME DESC
        """

        async with self._engine.connect() as conn:
            if self._disposing:
                return []

            result = await conn.execute(
                text(query),
                {"code": equip_code, "limit": limit},
            )
            rows = result.fetchall()
            return [self._map_status_row(row) for row in rows]

    # =========================================================================
    # Material Input Fetching (With Task Registration)
    # =========================================================================

    async def fetch_material_inputs(
        self,
        equip_code: str,
    ) -> List[MaterialInputRecord]:
        """Fetch material inputs with improved caching strategy."""

        # Early exit checks
        if not self._is_event_loop_usable():
            logger.debug("[MssqlAdapter] Event loop not available for material fetch: %s", equip_code)
            return []

        if not self.is_available:
            return []

        # Check cooldown
        if await self._cooldown_manager.is_on_cooldown(equip_code):
            remaining = await self._cooldown_manager.get_remaining(equip_code)
            logger.debug("[MssqlAdapter] %s on cooldown (%.0fs remaining)", equip_code, remaining)
            return []

        # ========== ENHANCED CACHE STRATEGY ==========
        # Use time-based cache key for better hit rate
        cache_key_base = f"material:{equip_code}"

        if self._cache:
            # Try current hour cache first (most specific)
            current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
            cache_key = f"{cache_key_base}:{current_hour.hour}"
            cached = await self._cache.get(cache_key)
            if cached is not None:
                logger.debug(f"[Cache HIT] {cache_key}")
                return cached

            # Try previous hour cache (fallback)
            prev_hour = current_hour - timedelta(hours=1)
            cache_key_prev = f"{cache_key_base}:{prev_hour.hour}"
            cached = await self._cache.get(cache_key_prev)
            if cached is not None:
                logger.debug(f"[Cache HIT] {cache_key_prev} (previous hour)")
                return cached
        # =============================================

        async with self._operation_semaphore:
            try:
                result = await self._execute_with_timeout(
                    self._do_fetch_material_inputs(equip_code),
                    timeout=self._config.material_timeout,
                    operation_name=f"fetch_material_inputs({equip_code})",
                )

                # Success - clear cooldown and cache result
                await self._cooldown_manager.clear_cooldown(equip_code)

                # ========== CACHE WITH HOUR-BASED KEY ==========
                if self._cache and result:
                    current_hour = datetime.now().replace(minute=0, second=0, microsecond=0)
                    cache_key = f"{cache_key_base}:{current_hour.hour}"

                    # Cache for remainder of hour + buffer
                    remaining_hour = 3600 - (datetime.now() - current_hour).total_seconds()
                    ttl = max(300, remaining_hour + 300)  # Min 5 minutes, typically ~1 hour

                    await self._cache.set(cache_key, result, ttl=ttl)
                    logger.debug(f"[Cache SET] {cache_key} (TTL: {ttl:.0f}s)")
                # ===============================================

                if result:
                    logger.info("[MssqlAdapter] Fetched %d materials for %s", len(result), equip_code)

                return result

            except (TimeoutError, asyncio.TimeoutError):
                duration = await self._cooldown_manager.start_cooldown(equip_code)
                logger.error(f"[MssqlAdapter] Material timeout for {equip_code}, " f"cooldown {duration:.0f}s")
                self._metrics.record_timeout(f"material_{equip_code}", self._config.material_timeout * 1000)
                return []

            except Exception as e:
                await self._cooldown_manager.start_cooldown(equip_code)
                if not self._is_disposed and not self._disposing:
                    logger.error(f"[MssqlAdapter] Material fetch error for {equip_code}: " f"{str(e)[:100]}")
                return []

    async def _do_fetch_material_inputs(
        self,
        equip_code: str,
    ) -> List[MaterialInputRecord]:
        """Execute material inputs query - OPTIMIZED WITHOUT INDEX."""
        if not self._engine or self._disposing:
            return []

        # ========== OPTIMIZED QUERY WITHOUT INDEX HINT ==========
        # Strategy: Limit date range progressively
        query = """
        -- First, try last 4 hours (most likely case)
        DECLARE @latest_lot NVARCHAR(100);
        DECLARE @cutoff_time DATETIME;
        
        -- Try 4 hours first
        SET @cutoff_time = DATEADD(HOUR, -4, GETDATE());
        
        SELECT TOP 1 @latest_lot = LOT_NO
        FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
        WHERE EQUIP_CODE = :equip_code
        AND FEED_TIME >= @cutoff_time
        ORDER BY FEED_TIME DESC;
        
        -- If no data in 4 hours, try 24 hours
        IF @latest_lot IS NULL
        BEGIN
            SET @cutoff_time = DATEADD(HOUR, -24, GETDATE());
            
            SELECT TOP 1 @latest_lot = LOT_NO
            FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
            WHERE EQUIP_CODE = :equip_code
            AND FEED_TIME >= @cutoff_time
            ORDER BY FEED_TIME DESC;
        END
        
        -- If still no data, try 48 hours (final attempt)
        IF @latest_lot IS NULL
        BEGIN
            SET @cutoff_time = DATEADD(HOUR, -48, GETDATE());
            
            SELECT TOP 1 @latest_lot = LOT_NO
            FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
            WHERE EQUIP_CODE = :equip_code
            AND FEED_TIME >= @cutoff_time
            ORDER BY FEED_TIME DESC;
        END
        
        -- Get materials for the LOT (if found)
        IF @latest_lot IS NOT NULL
        BEGIN
            SELECT TOP 50  -- Limit results
                LOT_NO,
                MATERIAL_BATCH,
                MATERIAL_NAME,
                MIN(FEED_TIME) as FEED_TIME,
                MAX(FEED_QTY) as FEED_QTY,
                MAX(ISNULL(FEED_USER, '')) as FEED_USER
            FROM yntti.dbo.RPT_FEEDING_DETAIL WITH (NOLOCK)
            WHERE LOT_NO = @latest_lot
            GROUP BY LOT_NO, MATERIAL_BATCH, MATERIAL_NAME
            ORDER BY MIN(FEED_TIME) ASC;
        END
        """
        # =======================================================

        try:
            async with self._engine.connect() as conn:
                if self._disposing:
                    return []

                result = await conn.execute(text(query), {"equip_code": equip_code})
                rows = result.fetchall()

                records = []
                for row in rows:
                    try:
                        record = MaterialInputRecord(
                            lot_no=str(row[0]).strip() if row[0] else "",
                            material_batch=str(row[1]).strip() if row[1] else "",
                            material_name=str(row[2]).strip() if row[2] else "",
                            feed_time=self._parse_datetime(row[3]) if row[3] else datetime.now(),
                            feed_qty=float(row[4]) if row[4] else 0.0,
                            feed_user=str(row[5]).strip() if row[5] else "",
                        )
                        records.append(record)
                    except Exception as e:
                        logger.debug("[MssqlAdapter] Parse error: %s", e)
                        continue

                return records

        except Exception as e:
            if "timeout" in str(e).lower():
                logger.error(
                    f"[MssqlAdapter] Material query timeout for {equip_code}. "
                    f"Consider reducing date range or adding index on (EQUIP_CODE, FEED_TIME)"
                )
            raise

    # =========================================================================
    # Run Time Calculations
    # =========================================================================

    async def fetch_today_run_times(
        self,
        equipment_codes: List[str],
    ) -> Dict[str, Optional[float]]:
        """
        Fetch today's run time in seconds for multiple equipment.

        Args:
            equipment_codes: List of equipment codes

        Returns:
            Dictionary mapping equipment code to run time seconds.
            Value is None if fetch failed for that device.
        """
        if not self._is_event_loop_usable():
            logger.debug("[MssqlAdapter] Event loop not available for fetch_today_run_times")
            return {code.upper(): None for code in equipment_codes}

        if not self.is_available or not equipment_codes:
            return {code.upper(): None for code in equipment_codes}

        # Batch in chunks
        results: Dict[str, Optional[float]] = {}

        for i in range(0, len(equipment_codes), self._config.max_batch_size):
            batch = equipment_codes[i : i + self._config.max_batch_size]

            async with self._operation_semaphore:
                try:
                    async with self._operation_context("fetch_today_run_times"):
                        batch_results = await self._do_fetch_today_run_times(batch)
                        results.update(batch_results)

                except Exception as e:
                    error_msg = str(e)
                    if "Event loop is closed" in error_msg or "closed" in error_msg.lower():
                        logger.debug("[MssqlAdapter] Event loop closed during run times fetch")
                    else:
                        if not self._is_disposed:
                            logger.error("[MssqlAdapter] Run times fetch error: %s", e)

                    results.update({code.upper(): None for code in batch})

        for code in equipment_codes:
            if code.upper() not in results:
                results[code.upper()] = None

        return results

    async def _do_fetch_today_run_times(
        self,
        equipment_codes: List[str],
    ) -> Dict[str, float]:
        """Execute today's run times query."""
        if not self._engine or self._disposing:
            logger.debug("[MssqlAdapter] Engine not available for run times")
            return {}

        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        total_seconds_today = (now - today_start).total_seconds()

        query_str = """
        SELECT 
            S.EQUIP_CODE,
            SUM(
                DATEDIFF(
                    SECOND,
                    CASE 
                        WHEN S.START_TIME > :today_start THEN S.START_TIME 
                        ELSE :today_start 
                    END,
                    CASE 
                        WHEN S.END_TIME IS NULL THEN :now
                        WHEN S.END_TIME < :now THEN S.END_TIME
                        ELSE :now 
                    END
                )
            ) as run_seconds
        FROM TT_EQ_STATUS S WITH (NOLOCK)
        WHERE S.EQUIP_CODE IN :codes
        AND S.EQUIP_STATUS = 1
        AND (S.DEL_FLAG = '0' OR S.DEL_FLAG IS NULL)
        AND S.START_TIME < :now
        AND (S.END_TIME > :today_start OR S.END_TIME IS NULL)
        AND (
            CASE 
                WHEN S.END_TIME IS NULL THEN :now
                WHEN S.END_TIME < :now THEN S.END_TIME
                ELSE :now 
            END
            >
            CASE 
                WHEN S.START_TIME > :today_start THEN S.START_TIME 
                ELSE :today_start 
            END
        )
        GROUP BY S.EQUIP_CODE
        """

        async with self._engine.connect() as conn:
            if self._disposing:
                return {}

            stmt = text(query_str)
            stmt = stmt.bindparams(bindparam("codes", expanding=True))

            result = await conn.execute(
                stmt,
                {
                    "codes": tuple(equipment_codes),
                    "today_start": today_start,
                    "now": now,
                },
            )
            rows = result.fetchall()

            logger.debug("[MssqlAdapter] Run times query returned %d rows for %d devices", len(rows), len(equipment_codes))

            run_times = {code.upper(): 0.0 for code in equipment_codes}
            for row in rows:
                code = str(row[0]).strip().upper()
                seconds = float(row[1]) if row[1] else 0.0
                run_times[code] = min(max(0.0, seconds), total_seconds_today)

            devices_with_data = [k for k, v in run_times.items() if v is not None]
            devices_without_data = [k for k, v in run_times.items() if v is None]
            if devices_without_data:
                logger.debug("[MssqlAdapter] No run time data for: %s", devices_without_data[:5])

            return run_times

    async def fetch_single_device_run_time(
        self,
        equipment_code: str,
    ) -> Optional[float]:
        """
        Fetch today's run time for a single device.

        Returns:
            Run time in seconds, or None if fetch failed.
        """
        results = await self.fetch_today_run_times([equipment_code])
        return results.get(equipment_code.upper())

    # =========================================================================
    # Health Check
    # =========================================================================

    async def health_check(self) -> bool:
        """
        Perform a health check on the database connection.

        Returns:
            True if connection is healthy
        """
        if not self._engine or self._is_disposed:
            return False

        async def _check():
            async with self._engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                return True

        return await self._health_monitor.check_health(lambda: self._execute_with_timeout(_check(), timeout=5.0, operation_name="health_check"))

    # =========================================================================
    # Management Methods
    # =========================================================================

    async def cancel_pending(self) -> None:
        """Cancel all pending operations."""
        async with self._task_lock:
            tasks_to_cancel = list(self._active_tasks)

        if tasks_to_cancel:
            logger.info("[MssqlAdapter] Cancelling %d pending operations", len(tasks_to_cancel))
            for task in tasks_to_cancel:
                if not task.done():
                    task.cancel()

            # Wait briefly for cancellation
            await asyncio.sleep(0.1)

    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker and clear all cooldowns."""
        self._circuit_breaker.reset()
        asyncio.create_task(self._cooldown_manager.clear_all())
        if self._cache:
            asyncio.create_task(self._cache.clear())
        logger.info("[MssqlAdapter] Circuit breaker and cooldowns reset")

    async def invalidate_cache(self, pattern: Optional[str] = None) -> None:
        """Invalidate cache entries."""
        if not self._cache:
            return

        if pattern:
            count = await self._cache.invalidate_prefix(pattern)
            logger.debug("[MssqlAdapter] Invalidated %d cache entries matching '%s'", count, pattern)
        else:
            await self._cache.clear()
            logger.debug("[MssqlAdapter] Cache cleared")

    def get_metrics(self) -> "RemoteMetrics":
        """Get adapter metrics in standard format."""
        from iFactory.application.ports.remote import RemoteMetrics

        metrics = RemoteMetrics()
        metrics.total_requests = self._metrics.total_operations
        metrics.successful_requests = self._metrics.successful_operations
        metrics.failed_requests = self._metrics.failed_operations

        return metrics

    # =========================================================================
    # Disposal
    # =========================================================================

    async def dispose(self) -> None:
        """Clean up adapter resources - IMPROVED."""
        if self._is_disposed:
            return

        logger.info("[MssqlAdapter] Starting disposal...")

        # Mark as disposing to prevent new operations
        async with self._lock:
            self._disposing = True
            active = self._active_count

        # Cancel all active tasks properly
        async with self._task_lock:
            tasks_to_cancel = list(self._active_tasks)

        if tasks_to_cancel:
            logger.info("[MssqlAdapter] Cancelling %d active tasks", len(tasks_to_cancel))
            for task in tasks_to_cancel:
                if not task.done():
                    task.cancel()

            # Wait for cancellation with timeout
            try:
                await asyncio.wait_for(asyncio.gather(*tasks_to_cancel, return_exceptions=True), timeout=1.0)
            except asyncio.TimeoutError:
                logger.debug("[MssqlAdapter] Task cancellation timeout")
            except Exception as e:
                logger.debug(f"[MssqlAdapter] Task cancellation error: {e}")

            self._active_tasks.clear()

        # Wait briefly for active operations to complete
        if active > 0:
            logger.debug("[MssqlAdapter] Waiting for %d operations...", active)
            await asyncio.sleep(0.3)

        self._is_disposed = True

        # Clear cache
        if self._cache:
            await self._cache.clear()

        # Proper engine disposal
        if self._engine:
            try:
                # Dispose engine (closes all connections)
                await self._engine.dispose()
                logger.info("[MssqlAdapter] Engine disposed")
            except Exception as e:
                logger.debug(f"[MssqlAdapter] Engine dispose error: {e}")
            finally:
                self._engine = None

        # Give connections time to close
        await asyncio.sleep(0.1)

        logger.info("[MssqlAdapter] Disposal complete")


# ============================================================================
# Internal Metrics Class
# ============================================================================


class _AdapterMetrics:
    """Internal metrics tracking for adapter - ENHANCED."""

    def __init__(self):
        self.total_operations = 0
        self.successful_operations = 0
        self.failed_operations = 0
        self.rejected_operations = 0
        self.timeout_operations = 0

        # ========== NEW METRICS ==========
        self.slow_queries: List[Tuple[str, float, datetime]] = []  # (name, ms, time)
        self.timeout_queries: List[Tuple[str, float, datetime]] = []
        self.max_history = 100
        # =================================

        self._lock = asyncio.Lock()

    def record_slow_query(self, operation: str, duration_ms: float) -> None:
        """Record slow query for analysis."""
        self.slow_queries.append((operation, duration_ms, datetime.now()))

        # Keep only recent
        if len(self.slow_queries) > self.max_history:
            self.slow_queries = self.slow_queries[-self.max_history :]

    def record_timeout(self, operation: str, duration_ms: float) -> None:
        """Record timeout for analysis."""
        self.timeout_operations += 1
        self.timeout_queries.append((operation, duration_ms, datetime.now()))

        # Keep only recent
        if len(self.timeout_queries) > self.max_history:
            self.timeout_queries = self.timeout_queries[-self.max_history :]

    def record_success(self) -> None:
        self.total_operations += 1
        self.successful_operations += 1

    def record_failure(self) -> None:
        self.total_operations += 1
        self.failed_operations += 1

    def record_rejected(self) -> None:
        self.rejected_operations += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get detailed metrics summary."""
        success_rate = self.successful_operations / self.total_operations if self.total_operations > 0 else 0.0

        # Calculate average slow query time
        avg_slow_time = sum(ms for _, ms, _ in self.slow_queries) / len(self.slow_queries) if self.slow_queries else 0.0

        # Get top slow operations
        slow_by_operation = defaultdict(list)
        for op, ms, _ in self.slow_queries:
            slow_by_operation[op].append(ms)

        top_slow = sorted(
            [(op, len(times), sum(times) / len(times)) for op, times in slow_by_operation.items()], key=lambda x: x[1], reverse=True  # Sort by count
        )[:5]

        return {
            "total": self.total_operations,
            "successful": self.successful_operations,
            "failed": self.failed_operations,
            "rejected": self.rejected_operations,
            "timeouts": self.timeout_operations,
            "success_rate": f"{success_rate:.1%}",
            "slow_queries": {
                "count": len(self.slow_queries),
                "avg_duration_ms": f"{avg_slow_time:.0f}",
                "top_operations": [{"operation": op, "count": count, "avg_ms": f"{avg_ms:.0f}"} for op, count, avg_ms in top_slow],
            },
            "recent_timeouts": [
                {"operation": op, "duration_ms": f"{ms:.0f}", "time": ts.strftime("%H:%M:%S")} for op, ms, ts in self.timeout_queries[-5:]
            ],
        }

    def to_dict(self) -> Dict[str, int]:
        """Legacy method for compatibility."""
        return {
            "total": self.total_operations,
            "successful": self.successful_operations,
            "failed": self.failed_operations,
            "rejected": self.rejected_operations,
            "timeouts": self.timeout_operations,
        }


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    "MssqlAdapter",
    "MssqlAdapterConfig",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerMetrics",
    "CircuitState",
    "RetryConfig",
    "MaterialInputRecord",
    "QueryCache",
    "CooldownManager",
    "ConnectionHealthMonitor",
]
