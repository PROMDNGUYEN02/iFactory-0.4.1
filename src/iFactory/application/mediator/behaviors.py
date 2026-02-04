# src/iFactory/application/mediator/behaviors.py
"""Pipeline Behaviors for cross-cutting concerns."""

from __future__ import annotations

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, Generic, List, Optional, Set, Type, TypeVar, Union

TRequest = TypeVar("TRequest")
TResponse = TypeVar("TResponse")

logger = logging.getLogger(__name__)


# ============================================================================
# Behavior Interface
# ============================================================================


class IPipelineBehavior(ABC, Generic[TRequest, TResponse]):
    """Pipeline behavior for intercepting request handling."""

    @abstractmethod
    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        """Process the request, optionally calling next handler."""
        pass


# ============================================================================
# Validation Behavior
# ============================================================================


class IValidator(ABC, Generic[TRequest]):
    """Validator interface for requests."""

    @abstractmethod
    async def validate(self, request: TRequest) -> Any:
        """Validate request, returning errors if invalid."""
        pass


class ValidationBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Validates requests before passing to handler."""

    def __init__(self, validators: Optional[Dict[Type, IValidator]] = None):
        self._validators = validators or {}

    def register(
        self,
        request_type: Type[TRequest],
        validator: IValidator[TRequest],
    ) -> None:
        """Register validator for request type."""
        self._validators[request_type] = validator

    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        validator = self._validators.get(type(request))

        if validator:
            result = await validator.validate(request)
            if hasattr(result, "is_failure") and result.is_failure:
                return result

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
    ):
        self._level = log_level
        self._include_request = include_request
        self._include_response = include_response

    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        request_name = type(request).__name__
        request_id = getattr(getattr(request, "metadata", None), "request_id", "N/A")
        if isinstance(request_id, str) and len(request_id) > 8:
            request_id = request_id[:8]

        log_msg = f"[{request_id}] Handling {request_name}"
        if self._include_request:
            log_msg += f" with {request}"
        logger.log(self._level, log_msg)

        start = time.perf_counter()

        try:
            response = await next_handler(request)
            elapsed = (time.perf_counter() - start) * 1000

            log_msg = f"[{request_id}] Completed {request_name} in {elapsed:.1f}ms"
            if self._include_response:
                log_msg += f" -> {response}"
            logger.log(self._level, log_msg)

            return response

        except Exception as e:
            elapsed = (time.perf_counter() - start) * 1000
            logger.error(f"[{request_id}] Failed {request_name} after {elapsed:.1f}ms: {e}")
            raise


# ============================================================================
# Caching Behavior
# ============================================================================


@dataclass
class CacheEntry:
    """Cached response with metadata."""

    response: Any
    cached_at: datetime = field(default_factory=datetime.now)
    hits: int = 0


class ICacheProvider(ABC):
    """Cache provider interface."""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        pass


class InMemoryCache(ICacheProvider):
    """Simple in-memory cache."""

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}
        self._ttls: Dict[str, datetime] = {}

    async def get(self, key: str) -> Optional[Any]:
        if key in self._ttls:
            if datetime.now() > self._ttls[key]:
                del self._cache[key]
                del self._ttls[key]
                return None

        entry = self._cache.get(key)
        if entry:
            entry.hits += 1
            return entry.response
        return None

    async def set(self, key: str, value: Any, ttl: int = 60) -> None:
        self._cache[key] = CacheEntry(response=value)
        self._ttls[key] = datetime.now() + timedelta(seconds=ttl)

    async def delete(self, key: str) -> None:
        self._cache.pop(key, None)
        self._ttls.pop(key, None)


class CachingBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Caches responses for cacheable requests."""

    def __init__(
        self,
        cache: Optional[ICacheProvider] = None,
        default_ttl: int = 60,
    ):
        self._cache = cache or InMemoryCache()
        self._default_ttl = default_ttl

    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        cache_key = getattr(request, "cache_key", None)
        if not cache_key:
            return await next_handler(request)

        cached = await self._cache.get(cache_key)
        if cached is not None:
            logger.debug(f"Cache hit: {cache_key}")
            return cached

        response = await next_handler(request)

        if hasattr(response, "is_failure") and response.is_failure:
            return response

        ttl = getattr(request, "cache_ttl", self._default_ttl)
        await self._cache.set(cache_key, response, ttl)
        logger.debug(f"Cache set: {cache_key} (ttl={ttl}s)")

        return response


# ============================================================================
# Transaction Behavior
# ============================================================================


class TransactionBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Wraps command handling in a database transaction."""

    def __init__(
        self,
        uow_factory: Callable,
        command_types: Optional[Set[Type]] = None,
    ):
        self._uow_factory = uow_factory
        self._command_types = command_types or set()

    def register_command(self, command_type: Type) -> None:
        """Register a type as a command."""
        self._command_types.add(command_type)

    def _is_command(self, request: TRequest) -> bool:
        """Check if request is a command."""
        request_name = type(request).__name__
        return (
            type(request) in self._command_types
            or "Command" in request_name
            or "Create" in request_name
            or "Update" in request_name
            or "Delete" in request_name
            or "Sync" in request_name
        )

    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        if not self._is_command(request):
            return await next_handler(request)

        async with self._uow_factory() as uow:
            if hasattr(request, "_uow"):
                object.__setattr__(request, "_uow", uow)

            response = await next_handler(request)

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
    ):
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._retryable = retryable_exceptions

    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        last_exception = None

        for attempt in range(self._max_retries + 1):
            try:
                return await next_handler(request)
            except self._retryable as e:
                last_exception = e
                if attempt < self._max_retries:
                    delay = min(
                        self._base_delay * (2**attempt),
                        self._max_delay,
                    )
                    logger.warning(f"Retry {attempt + 1}/{self._max_retries} after {delay:.2f}s: {e}")
                    await asyncio.sleep(delay)

        raise last_exception  # type: ignore


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


class MetricsBehavior(IPipelineBehavior[TRequest, TResponse]):
    """Collects metrics for request handling."""

    def __init__(self):
        self._metrics: Dict[str, RequestMetrics] = {}

    def get_metrics(
        self,
        request_type: Optional[str] = None,
    ) -> Union[RequestMetrics, Dict[str, RequestMetrics]]:
        if request_type:
            return self._metrics.get(request_type, RequestMetrics(request_type))
        return self._metrics.copy()

    async def handle(
        self,
        request: TRequest,
        next_handler: Callable[[TRequest], Awaitable[TResponse]],
    ) -> TResponse:
        request_type = type(request).__name__

        if request_type not in self._metrics:
            self._metrics[request_type] = RequestMetrics(request_type)

        metrics = self._metrics[request_type]
        start = time.perf_counter()

        try:
            response = await next_handler(request)

            metrics.total_count += 1
            metrics.total_duration_ms += (time.perf_counter() - start) * 1000

            if hasattr(response, "is_success"):
                if response.is_success:
                    metrics.success_count += 1
                else:
                    metrics.failure_count += 1
            else:
                metrics.success_count += 1

            return response

        except Exception:
            metrics.total_count += 1
            metrics.failure_count += 1
            metrics.total_duration_ms += (time.perf_counter() - start) * 1000
            raise


__all__ = [
    "IPipelineBehavior",
    "IValidator",
    "ValidationBehavior",
    "LoggingBehavior",
    "ICacheProvider",
    "InMemoryCache",
    "CachingBehavior",
    "TransactionBehavior",
    "RetryBehavior",
    "MetricsBehavior",
    "RequestMetrics",
    "CacheEntry",
]
