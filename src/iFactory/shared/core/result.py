"""
Railway-Oriented Programming with Result Pattern.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar, Generic, Callable, Optional, List, Awaitable, Iterator
from enum import StrEnum, auto
from datetime import datetime

T = TypeVar("T")
E = TypeVar("E")
U = TypeVar("U")


class ErrorSeverity(StrEnum):
    """Error severity levels."""

    INFO = auto()
    WARNING = auto()
    ERROR = auto()
    CRITICAL = auto()


@dataclass(frozen=True, slots=True)
class Error:
    """Structured error with context."""

    code: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    details: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
        }


class Errors:
    """Factory for common errors."""

    @staticmethod
    def not_found(entity: str, identifier: str) -> Error:
        return Error(
            code="NOT_FOUND",
            message=f"{entity} with id '{identifier}' not found",
            details={"entity": entity, "identifier": identifier},
        )

    @staticmethod
    def validation(message: str, field: Optional[str] = None) -> Error:
        details = {"field": field} if field else {}
        return Error(
            code="VALIDATION_ERROR",
            message=message,
            severity=ErrorSeverity.WARNING,
            details=details,
        )

    @staticmethod
    def database(message: str, operation: str = "unknown") -> Error:
        return Error(
            code="DATABASE_ERROR",
            message=message,
            severity=ErrorSeverity.ERROR,
            details={"operation": operation},
        )

    @staticmethod
    def external_service(service: str, message: str) -> Error:
        return Error(
            code="EXTERNAL_SERVICE_ERROR",
            message=message,
            severity=ErrorSeverity.ERROR,
            details={"service": service},
        )

    @staticmethod
    def timeout(operation: str, timeout_seconds: float) -> Error:
        return Error(
            code="TIMEOUT",
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            severity=ErrorSeverity.WARNING,
            details={"operation": operation, "timeout": timeout_seconds},
        )


@dataclass(frozen=True, slots=True)
class Result(Generic[T, E]):
    """Result monad for railway-oriented programming."""

    _value: Optional[T] = field(default=None)
    _error: Optional[E] = field(default=None)
    _is_success: bool = field(default=True)

    @classmethod
    def success(cls, value: T) -> "Result[T, E]":
        return cls(_value=value, _error=None, _is_success=True)

    @classmethod
    def failure(cls, error: E) -> "Result[T, E]":
        return cls(_value=None, _error=error, _is_success=False)

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        code: str = "EXCEPTION",
        source: Optional[str] = None,
    ) -> "Result[T, Error]":
        error = Error(
            code=code,
            message=str(exception),
            severity=ErrorSeverity.ERROR,
            details={"exception_type": type(exception).__name__},
            source=source,
        )
        return cls.failure(error)

    @property
    def is_success(self) -> bool:
        return self._is_success

    @property
    def is_failure(self) -> bool:
        return not self._is_success

    @property
    def value(self) -> T:
        if not self._is_success:
            raise ValueError(f"Cannot get value from failure: {self._error}")
        return self._value  # type: ignore

    @property
    def error(self) -> E:
        if self._is_success:
            raise ValueError("Cannot get error from success")
        return self._error  # type: ignore

    def unwrap(self) -> T:
        return self.value

    def unwrap_or(self, default: T) -> T:
        return self._value if self._is_success else default  # type: ignore

    def to_optional(self) -> Optional[T]:
        return self._value if self._is_success else None

    def __bool__(self) -> bool:
        return self._is_success

    def __repr__(self) -> str:
        if self._is_success:
            return f"Success({self._value!r})"
        return f"Failure({self._error!r})"


async def async_map(
    result: Result[T, E],
    func: Callable[[T], Awaitable[U]],
) -> Result[U, E]:
    if result.is_success:
        try:
            value = await func(result.value)
            return Result.success(value)
        except Exception as e:
            return Result.from_exception(e)
    return Result.failure(result.error)


async def async_flat_map(
    result: Result[T, E],
    func: Callable[[T], Awaitable[Result[U, E]]],
) -> Result[U, E]:
    if result.is_success:
        try:
            return await func(result.value)
        except Exception as e:
            return Result.from_exception(e)
    return Result.failure(result.error)


def collect_results(results: List[Result[T, E]]) -> Result[List[T], List[E]]:
    successes: List[T] = []
    failures: List[E] = []
    for r in results:
        if r.is_success:
            successes.append(r.value)
        else:
            failures.append(r.error)
    if failures:
        return Result.failure(failures)
    return Result.success(successes)


def first_success(results: Iterator[Result[T, E]]) -> Result[T, List[E]]:
    errors: List[E] = []
    for r in results:
        if r.is_success:
            return Result.success(r.value)
        errors.append(r.error)
    return Result.failure(errors)


__all__ = [
    "Result",
    "Error",
    "Errors",
    "ErrorSeverity",
    "async_map",
    "async_flat_map",
    "collect_results",
    "first_success",
]
