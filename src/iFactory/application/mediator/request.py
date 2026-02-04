# src/iFactory/application/mediator/request.py
"""Request/Response pattern for CQRS."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, TypeVar
from uuid import uuid4

TResponse = TypeVar("TResponse")


# ============================================================================
# Interfaces
# ============================================================================


class IRequest(ABC, Generic[TResponse]):
    """Base interface for all requests."""

    pass


class IRequestHandler(ABC, Generic[TResponse]):
    """Handler interface for processing requests."""

    @abstractmethod
    async def handle(self, request: IRequest[TResponse]) -> TResponse:
        """Handle the request and return response."""
        pass


# ============================================================================
# Metadata
# ============================================================================


@dataclass(frozen=True)
class RequestMetadata:
    """Metadata attached to requests."""

    request_id: str = field(default_factory=lambda: str(uuid4()))
    correlation_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: str | None = None
    source: str = ""

    def __post_init__(self) -> None:
        if not self.correlation_id:
            object.__setattr__(self, "correlation_id", self.request_id)


# ============================================================================
# Base Classes
# ============================================================================


@dataclass(frozen=True)
class Request(IRequest[TResponse], Generic[TResponse]):
    """Base class for all requests with metadata."""

    metadata: RequestMetadata = field(default_factory=RequestMetadata)


@dataclass(frozen=True)
class Command(Request[TResponse], Generic[TResponse]):
    """Base class for commands (write operations)."""

    pass


@dataclass(frozen=True)
class Query(Request[TResponse], Generic[TResponse]):
    """Base class for queries (read operations)."""

    pass


# ============================================================================
# Errors
# ============================================================================


class HandlerNotFoundError(Exception):
    """Raised when no handler is registered for a request type."""

    def __init__(self, request_type: type) -> None:
        self.request_type = request_type
        super().__init__(f"No handler registered for {request_type.__name__}")


__all__ = [
    "IRequest",
    "IRequestHandler",
    "Request",
    "Command",
    "Query",
    "RequestMetadata",
    "HandlerNotFoundError",
]
