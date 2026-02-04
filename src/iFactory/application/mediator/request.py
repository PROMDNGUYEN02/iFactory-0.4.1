# src/iFactory/application/mediator/request.py
"""
Request/Response pattern for CQRS.

Provides base classes for Commands (write) and Queries (read) operations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, Optional, TypeVar, ClassVar
from uuid import uuid4

TResponse = TypeVar("TResponse")


# ============================================================================
# Interfaces
# ============================================================================


class IRequest(ABC, Generic[TResponse]):
    """
    Base interface for all requests (commands and queries).

    Type parameter TResponse indicates the expected response type.
    """

    pass


class IRequestHandler(ABC, Generic[TResponse]):
    """
    Handler interface for processing requests.

    Each request type should have exactly one handler.
    """

    @abstractmethod
    async def handle(self, request: IRequest[TResponse]) -> TResponse:
        """
        Handle the request and return response.

        Args:
            request: The request to handle

        Returns:
            Response of type TResponse
        """
        pass


# ============================================================================
# Metadata
# ============================================================================


@dataclass(frozen=True, slots=True)
class RequestMetadata:
    """
    Metadata attached to requests for tracing and auditing.

    Attributes:
        request_id: Unique identifier for this request
        correlation_id: ID linking related requests (defaults to request_id)
        causation_id: ID of request that caused this one
        timestamp: When the request was created
        user_id: ID of user making the request
        source: Origin of the request (e.g., "api", "scheduler", "ui")
    """

    request_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: Optional[str] = None
    causation_id: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    source: str = ""

    def __post_init__(self) -> None:
        # Default correlation_id to request_id if not provided
        if self.correlation_id is None:
            object.__setattr__(self, "correlation_id", self.request_id)

    def derive(self) -> "RequestMetadata":
        """
        Create derived metadata for a caused request.

        Links causation to this request and inherits correlation.
        """
        return RequestMetadata(
            correlation_id=self.correlation_id,
            causation_id=self.request_id,
            user_id=self.user_id,
            source=self.source,
        )

    def with_source(self, source: str) -> "RequestMetadata":
        """Create copy with different source."""
        return RequestMetadata(
            request_id=self.request_id,
            correlation_id=self.correlation_id,
            causation_id=self.causation_id,
            timestamp=self.timestamp,
            user_id=self.user_id,
            source=source,
        )


# ============================================================================
# Base Classes
# ============================================================================


@dataclass(frozen=True)
class Request(IRequest[TResponse], Generic[TResponse]):
    """
    Base class for all requests with metadata.

    Provides:
    - Immutability (frozen dataclass)
    - Request metadata for tracing
    - Short request_id property
    """

    metadata: RequestMetadata = field(default_factory=RequestMetadata)

    @property
    def request_id(self) -> str:
        """Shortcut to metadata.request_id."""
        return self.metadata.request_id

    @property
    def short_id(self) -> str:
        """Short version of request_id for logging."""
        return self.request_id[:8] if self.request_id else "N/A"


@dataclass(frozen=True)
class Command(Request[TResponse], Generic[TResponse]):
    """
    Base class for commands (write operations).

    Commands:
    - Modify state
    - Should be validated before execution
    - May return a result indicating success/failure
    - Should be idempotent when possible

    Example:
        @dataclass(frozen=True)
        class CreateOrderCommand(Command[Result[Order, Error]]):
            customer_id: str
            items: Tuple[OrderItem, ...]
    """

    pass


@dataclass(frozen=True)
class Query(Request[TResponse], Generic[TResponse]):
    """
    Base class for queries (read operations).

    Queries:
    - Do not modify state
    - Should be cacheable when appropriate
    - Return data or projections

    Example:
        @dataclass(frozen=True)
        class GetOrderQuery(Query[Optional[OrderDTO]]):
            order_id: str

            @property
            def cache_key(self) -> str:
                return f"order:{self.order_id}"

            cache_ttl: int = 60  # seconds
    """

    pass


# ============================================================================
# Cacheable Mixin
# ============================================================================


class CacheableRequest(Generic[TResponse]):
    """
    Mixin for requests that support caching.

    Implement cache_key property and optionally cache_ttl.
    """

    @property
    def cache_key(self) -> Optional[str]:
        """
        Cache key for this request.

        Return None to disable caching.
        """
        return None

    cache_ttl: ClassVar[int] = 60  # Default TTL in seconds


# ============================================================================
# Errors
# ============================================================================


class HandlerNotFoundError(Exception):
    """Raised when no handler is registered for a request type."""

    def __init__(self, request_type: type) -> None:
        self.request_type = request_type
        super().__init__(f"No handler registered for {request_type.__name__}")


class RequestValidationError(Exception):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str,
        errors: Optional[dict] = None,
    ) -> None:
        self.errors = errors or {}
        super().__init__(message)


__all__ = [
    # Interfaces
    "IRequest",
    "IRequestHandler",
    # Base classes
    "Request",
    "Command",
    "Query",
    # Metadata
    "RequestMetadata",
    # Mixins
    "CacheableRequest",
    # Errors
    "HandlerNotFoundError",
    "RequestValidationError",
]
