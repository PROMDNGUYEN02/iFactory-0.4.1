# src/iFactory/application/mediator/behaviors.py
"""
Pipeline Behaviors for cross-cutting concerns.

Behaviors wrap request handling to add functionality like:
- Logging
- Validation
- Caching
- Transactions
- Retry logic
- Metrics collection
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")

logger = logging.getLogger(__name__)

# Type alias for next handler in pipeline
NextHandler = Callable[[TRequest], Awaitable[TResponse]]


# ============================================================================
# Behavior Interface
# ============================================================================


class IPipelineBehavior(ABC, Generic[TRequest, TResponse]):
    """
    Pipeline behavior for intercepting request handling.

    Behaviors are executed in order of registration, wrapping the
    actual handler. Each behavior can:
    - Execute code before the handler
    - Execute code after the handler
    - Modify the request
    - Short-circuit and return early
    - Catch and handle exceptions
    """

    @abstractmethod
    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        """
        Process the request, optionally calling next handler.

        Args:
            request: The request being processed
            next_handler: The next handler in the pipeline

        Returns:
            Response from handler or behavior
        """
        pass


# ============================================================================
# Validation Behavior
# ============================================================================


class IValidator(ABC, Generic[TRequest]):
    """Validator interface for requests."""

    @abstractmethod
    async def validate(self, request: TRequest) -> "ValidationResult":
        """
        Validate request.

        Returns:
            ValidationResult with success status and any errors
        """
        pass


@dataclass
class ValidationResult:
    """Result of validation."""

    is_valid: bool = True
    errors: Dict[str, List[str]] = field(default_factory=dict)

    def add_error(self, field: str, message: str) -> None:
        """Add validation error."""
        if field not in self.errors:
            self.errors[field] = []
        self.errors[field].append(message)
        self.is_valid = False

    @classmethod
    def success(cls) -> "ValidationResult":
        """Create successful result."""
        return cls(is_valid=True)

    @classmethod
    def failure(cls, errors: Dict[str, List[str]]) -> "ValidationResult":
        """Create failed result."""
        return cls(is_valid=False, errors=errors)


class ValidationBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Validates requests before passing to handler."""

    def __init__(
        self,
        validators: Optional[Dict[Type, IValidator]] = None,
        raise_on_failure: bool = True,
    ) -> None:
        """
        Initialize validation behavior.

        Args:
            validators: Dict mapping request types to validators
            raise_on_failure: Whether to raise exception on validation failure
        """
        self._validators: Dict[Type, IValidator] = validators or {}
        self._raise_on_failure = raise_on_failure

    def register(
        self,
        request_type: Type[TRequest],
        validator: IValidator[TRequest],
    ) -> "ValidationBehavior":
        """Register validator for request type."""
        self._validators[request_type] = validator
        return self

    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        validator = self._validators.get(type(request))

        if validator:
            result = await validator.validate(request)

            if not result.is_valid:
                if self._raise_on_failure:
                    from .request import RequestValidationError

                    raise RequestValidationError(
                        "Validation failed",
                        errors=result.errors,
                    )
                # If response has a failure factory, use it
                if hasattr(result, "to_response"):
                    return result.to_response()

        return await next_handler(request)


# ============================================================================
# Logging Behavior
# ============================================================================


class LoggingBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Logs request handling with timing."""

    def __init__(
        self,
        log_level: int = logging.INFO,
        include_request: bool = False,
        include_response: bool = False,
        slow_threshold_ms: float = 1000.0,
    ) -> None:
        """
        Initialize logging behavior.

        Args:
            log_level: Log level for normal messages
            include_request: Whether to log request details
            include_response: Whether to log response details
            slow_threshold_ms: Threshold for warning about slow requests
        """
        self._level = log_level
        self._include_request = include_request
        self._include_response = include_response
        self._slow_threshold_ms = slow_threshold_ms

    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        request_name = type(request).__name__
        request_id = getattr(getattr(request, "metadata", None), "request_id", "N/A")
        short_id = request_id[:8] if isinstance(request_id, str) else request_id

        # Log start
        log_msg = f"[{short_id}] Handling {request_name}"
        if self._include_request:
            log_msg += f" with {request}"
        logger.log(self._level, log_msg)

        start = time.perf_counter()

        try:
            response = await next_handler(request)
            elapsed_ms = (time.perf_counter() - start) * 1000

            # Log completion
            log_msg = f"[{short_id}] Completed {request_name} in {elapsed_ms:.1f}ms"
            if self._include_response:
                log_msg += f" -> {response}"

            # Warn if slow
            if elapsed_ms > self._slow_threshold_ms:
                logger.warning(f"[{short_id}] SLOW: {request_name} took {elapsed_ms:.1f}ms")
            else:
                logger.log(self._level, log_msg)

            return response

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            logger.error(f"[{short_id}] Failed {request_name} after {elapsed_ms:.1f}ms: {e}")
            raise


# ============================================================================
# Caching Behavior
# ============================================================================


@dataclass
class CacheEntry:
    """Cached response with metadata."""

    response: Any
    cached_at: datetime = field(default_factory=datetime.now)
    expires_at: Optional[datetime] = None
    hits: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at


class ICacheProvider(ABC):
    """Cache provider interface for behaviors."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value by key."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        """Set value with TTL."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key."""
        pass


class InMemoryCache(ICacheProvider):
    """Simple in-memory cache for behaviors."""

    def __init__(self, max_size: int = 1000) -> None:
        self._cache: Dict[str, CacheEntry] = {}
        self._max_size = max_size
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)

        if entry is None:
            self._misses += 1
            return None

        if entry.is_expired:
            del self._cache[key]
            self._misses += 1
            return None

        entry.hits += 1
        self._hits += 1
        return entry.response

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        # Evict oldest entries if at capacity
        if len(self._cache) >= self._max_size:
            oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].cached_at)
            del self._cache[oldest_key]

        self._cache[key] = CacheEntry(
            response=value,
            expires_at=datetime.now() + timedelta(seconds=ttl),
        )

    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": self._hits / total if total > 0 else 0,
            "size": len(self._cache),
            "max_size": self._max_size,
        }


class CachingBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Caches responses for cacheable requests."""

    def __init__(
        self,
        cache: Optional[ICacheProvider] = None,
        default_ttl: int = 60,
    ) -> None:
        """
        Initialize caching behavior.

        Args:
            cache: Cache provider (defaults to InMemoryCache)
            default_ttl: Default TTL in seconds
        """
        self._cache = cache or InMemoryCache()
        self._default_ttl = default_ttl

    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        # Get cache key from request
        cache_key = getattr(request, "cache_key", None)
        if not cache_key:
            return await next_handler(request)

        # Try cache
        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        # Execute handler
        response = await next_handler(request)

        # Don't cache failures
        if hasattr(response, "is_failure") and response.is_failure:
            return response

        # Cache response
        ttl = getattr(request, "cache_ttl", self._default_ttl)
        await self._cache.set(cache_key, response, ttl)
        logger.debug(f"Cache set: {cache_key} (ttl={ttl}s)")

        return response

    async def invalidate(self, key: str) -> None:
        """Invalidate a cache key."""
        await self._cache.delete(key)


# ============================================================================
# Transaction Behavior
# ============================================================================


class TransactionBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Wraps command handling in a database transaction."""

    def __init__(
        self,
        uow_factory: Callable,
        command_types: Optional[Set[Type]] = None,
    ) -> None:
        """
        Initialize transaction behavior.

        Args:
            uow_factory: Factory for creating Unit of Work
            command_types: Set of types to treat as commands
        """
        self._uow_factory = uow_factory
        self._command_types = command_types or set()

    def register_command(self, command_type: Type) -> "TransactionBehavior":
        """Register a type as a command."""
        self._command_types.add(command_type)
        return self

    def _is_command(self, request: TRequest) -> bool:
        """Check if request is a command (needs transaction)."""
        request_type = type(request)
        request_name = request_type.__name__

        return (
            request_type in self._command_types
            or "Command" in request_name
            or any(word in request_name for word in ["Create", "Update", "Delete", "Sync", "Save", "Remove"])
        )

    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        if not self._is_command(request):
            return await next_handler(request)

        async with self._uow_factory() as uow:
            # Inject UoW if request expects it
            if hasattr(request, "_uow"):
                object.__setattr__(request, "_uow", uow)

            response = await next_handler(request)

            # Rollback on failure, commit on success
            if hasattr(response, "is_failure") and response.is_failure:
                await uow.rollback()
            else:
                await uow.commit()

            return response


# ============================================================================
# Retry Behavior
# ============================================================================


class RetryBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Retries failed requests with exponential backoff."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 0.1,
        max_delay: float = 5.0,
        retryable_exceptions: tuple = (Exception,),
        non_retryable_exceptions: tuple = (),
    ) -> None:
        """
        Initialize retry behavior.

        Args:
            max_retries: Maximum retry attempts
            base_delay: Base delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            retryable_exceptions: Exceptions to retry
            non_retryable_exceptions: Exceptions to never retry
        """
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._retryable = retryable_exceptions
        self._non_retryable = non_retryable_exceptions

    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        last_exception: Optional[Exception] = None
        request_name = type(request).__name__

        for attempt in range(self._max_retries + 1):
            try:
                return await next_handler(request)

            except self._non_retryable:
                # Never retry these
                raise

            except self._retryable as e:
                last_exception = e

                if attempt < self._max_retries:
                    delay = min(
                        self._base_delay * (2**attempt),
                        self._max_delay,
                    )
                    logger.warning(f"Retry {attempt + 1}/{self._max_retries} for " f"{request_name} after {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)

        # All retries exhausted
        assert last_exception is not None
        raise last_exception


# ============================================================================
# Metrics Behavior
# ============================================================================


@dataclass
class RequestMetrics:
    """Collected metrics for a request type."""

    request_type: str
    total_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration_ms: float = 0.0
    min_duration_ms: float = float("inf")
    max_duration_ms: float = 0.0

    @property
    def avg_duration_ms(self) -> float:
        if self.total_count == 0:
            return 0.0
        return self.total_duration_ms / self.total_count

    @property
    def success_rate(self) -> float:
        if self.total_count == 0:
            return 1.0
        return self.success_count / self.total_count

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_type": self.request_type,
            "total_count": self.total_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": f"{self.success_rate:.2%}",
            "avg_duration_ms": f"{self.avg_duration_ms:.1f}",
            "min_duration_ms": f"{self.min_duration_ms:.1f}" if self.min_duration_ms != float("inf") else "N/A",
            "max_duration_ms": f"{self.max_duration_ms:.1f}",
        }


class MetricsBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Collects metrics for request handling."""

    def __init__(self) -> None:
        self._metrics: Dict[str, RequestMetrics] = {}
        self._start_time = datetime.now()

    def get_metrics(
        self,
        request_type: Optional[str] = None,
    ) -> Union[RequestMetrics, Dict[str, RequestMetrics], None]:
        """Get metrics for specific type or all types."""
        if request_type:
            return self._metrics.get(request_type)
        return self._metrics.copy()

    def reset(self) -> None:
        """Reset all metrics."""
        self._metrics.clear()
        self._start_time = datetime.now()

    async def handle(
        self,
        request: TRequest,
        next_handler: NextHandler[TRequest, TResponse],
    ) -> TResponse:
        request_type = type(request).__name__

        if request_type not in self._metrics:
            self._metrics[request_type] = RequestMetrics(request_type)

        metrics = self._metrics[request_type]
        start = time.perf_counter()

        try:
            response = await next_handler(request)

            duration_ms = (time.perf_counter() - start) * 1000
            metrics.total_count += 1
            metrics.total_duration_ms += duration_ms
            metrics.min_duration_ms = min(metrics.min_duration_ms, duration_ms)
            metrics.max_duration_ms = max(metrics.max_duration_ms, duration_ms)

            # Check if response indicates success/failure
            if hasattr(response, "is_success"):
                if response.is_success:
                    metrics.success_count += 1
                else:
                    metrics.failure_count += 1
            else:
                metrics.success_count += 1

            return response

        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            metrics.total_count += 1
            metrics.failure_count += 1
            metrics.total_duration_ms += duration_ms
            raise

    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics."""
        total_requests = sum(m.total_count for m in self._metrics.values())
        total_successes = sum(m.success_count for m in self._metrics.values())

        return {
            "uptime_seconds": (datetime.now() - self._start_time).total_seconds(),
            "total_requests": total_requests,
            "total_successes": total_successes,
            "overall_success_rate": total_successes / total_requests if total_requests > 0 else 1.0,
            "request_types": len(self._metrics),
            "by_type": {k: v.to_dict() for k, v in self._metrics.items()},
        }


__all__ = [
    # Interface
    "IPipelineBehavior",
    "NextHandler",
    # Validation
    "IValidator",
    "ValidationResult",
    "ValidationBehavior",
    # Logging
    "LoggingBehavior",
    # Caching
    "ICacheProvider",
    "InMemoryCache",
    "CacheEntry",
    "CachingBehavior",
    # Transaction
    "TransactionBehavior",
    # Retry
    "RetryBehavior",
    # Metrics
    "MetricsBehavior",
    "RequestMetrics",
]
