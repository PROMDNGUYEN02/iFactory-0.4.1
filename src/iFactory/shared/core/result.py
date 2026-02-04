# src/iFactory/shared/core/result.py
"""
Railway-Oriented Programming with Result Pattern.

Provides a type-safe way to handle success/failure without exceptions.
Supports both sync and async operations with monadic composition.

Features:
- Type-safe Result monad
- Structured Error with severity levels
- Factory methods for common errors
- Monadic operations (map, flat_map, etc.)
- Async support
- Result collection utilities
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Tuple,
    TypeVar,
    Union,
    overload,
)

T = TypeVar("T")  # Success type
E = TypeVar("E")  # Error type
U = TypeVar("U")  # Mapped type
F = TypeVar("F")  # Mapped error type


# ============================================================================
# Error Types
# ============================================================================


class ErrorSeverity(StrEnum):
    """Error severity levels for logging and handling decisions."""

    INFO = auto()  # Informational, not really an error
    WARNING = auto()  # Something unexpected but recoverable
    ERROR = auto()  # An error that prevented the operation
    CRITICAL = auto()  # Critical error requiring immediate attention


@dataclass(frozen=True, slots=True)
class Error:
    """
    Structured error with context for detailed error handling.

    Attributes:
        code: Machine-readable error code (e.g., "NOT_FOUND", "VALIDATION_ERROR")
        message: Human-readable error message
        severity: Error severity level
        details: Additional context as key-value pairs
        timestamp: When the error occurred
        source: Where the error originated (e.g., "DeviceRepository", "RemoteAPI")
        inner_error: Wrapped inner error for error chaining
    """

    code: str
    message: str
    severity: ErrorSeverity = ErrorSeverity.ERROR
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: Optional[str] = None
    inner_error: Optional["Error"] = None

    def with_source(self, source: str) -> "Error":
        """Create new error with source set."""
        return Error(
            code=self.code,
            message=self.message,
            severity=self.severity,
            details=self.details,
            timestamp=self.timestamp,
            source=source,
            inner_error=self.inner_error,
        )

    def with_details(self, **kwargs: Any) -> "Error":
        """Create new error with additional details."""
        return Error(
            code=self.code,
            message=self.message,
            severity=self.severity,
            details={**self.details, **kwargs},
            timestamp=self.timestamp,
            source=self.source,
            inner_error=self.inner_error,
        )

    def wrap(self, outer_message: str, outer_code: Optional[str] = None) -> "Error":
        """Wrap this error in another error (error chaining)."""
        return Error(
            code=outer_code or self.code,
            message=outer_message,
            severity=self.severity,
            details=self.details,
            source=self.source,
            inner_error=self,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        result = {
            "code": self.code,
            "message": self.message,
            "severity": self.severity.value,
            "details": self.details,
            "timestamp": self.timestamp.isoformat(),
        }
        if self.source:
            result["source"] = self.source
        if self.inner_error:
            result["inner_error"] = self.inner_error.to_dict()
        return result

    def __str__(self) -> str:
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return f"Error(code={self.code!r}, message={self.message!r}, severity={self.severity})"


class Errors:
    """Factory for common error types."""

    @staticmethod
    def not_found(
        entity: str,
        identifier: Any,
        message: Optional[str] = None,
    ) -> Error:
        """Resource not found error."""
        return Error(
            code="NOT_FOUND",
            message=message or f"{entity} with id '{identifier}' not found",
            severity=ErrorSeverity.WARNING,
            details={"entity": entity, "identifier": str(identifier)},
        )

    @staticmethod
    def validation(
        message: str,
        field: Optional[str] = None,
        value: Any = None,
    ) -> Error:
        """Validation error."""
        details: Dict[str, Any] = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]  # Truncate long values
        return Error(
            code="VALIDATION_ERROR",
            message=message,
            severity=ErrorSeverity.WARNING,
            details=details,
        )

    @staticmethod
    def validation_many(
        errors: Dict[str, List[str]],
    ) -> Error:
        """Multiple validation errors."""
        error_count = sum(len(e) for e in errors.values())
        return Error(
            code="VALIDATION_ERROR",
            message=f"Validation failed with {error_count} error(s)",
            severity=ErrorSeverity.WARNING,
            details={"errors": errors},
        )

    @staticmethod
    def database(
        message: str,
        operation: str = "unknown",
        table: Optional[str] = None,
    ) -> Error:
        """Database error."""
        details: Dict[str, Any] = {"operation": operation}
        if table:
            details["table"] = table
        return Error(
            code="DATABASE_ERROR",
            message=message,
            severity=ErrorSeverity.ERROR,
            details=details,
        )

    @staticmethod
    def external_service(
        service: str,
        message: str,
        status_code: Optional[int] = None,
    ) -> Error:
        """External service error."""
        details: Dict[str, Any] = {"service": service}
        if status_code:
            details["status_code"] = status_code
        return Error(
            code="EXTERNAL_SERVICE_ERROR",
            message=f"Service '{service}' failed: {message}",
            severity=ErrorSeverity.ERROR,
            details=details,
        )

    @staticmethod
    def timeout(
        operation: str,
        timeout_seconds: float,
    ) -> Error:
        """Timeout error."""
        return Error(
            code="TIMEOUT",
            message=f"Operation '{operation}' timed out after {timeout_seconds}s",
            severity=ErrorSeverity.WARNING,
            details={"operation": operation, "timeout_seconds": timeout_seconds},
        )

    @staticmethod
    def unauthorized(
        message: str = "Unauthorized access",
        required_permission: Optional[str] = None,
    ) -> Error:
        """Authorization error."""
        details: Dict[str, Any] = {}
        if required_permission:
            details["required_permission"] = required_permission
        return Error(
            code="UNAUTHORIZED",
            message=message,
            severity=ErrorSeverity.WARNING,
            details=details,
        )

    @staticmethod
    def forbidden(
        resource: str,
        action: str,
    ) -> Error:
        """Forbidden access error."""
        return Error(
            code="FORBIDDEN",
            message=f"Access denied: cannot {action} {resource}",
            severity=ErrorSeverity.WARNING,
            details={"resource": resource, "action": action},
        )

    @staticmethod
    def conflict(
        entity: str,
        reason: str,
        identifier: Optional[str] = None,
    ) -> Error:
        """Conflict error."""
        details: Dict[str, Any] = {"entity": entity, "reason": reason}
        if identifier:
            details["identifier"] = identifier
        return Error(
            code="CONFLICT",
            message=f"Conflict with {entity}: {reason}",
            severity=ErrorSeverity.WARNING,
            details=details,
        )

    @staticmethod
    def concurrency(
        entity: str,
        identifier: str,
        expected_version: Optional[int] = None,
        actual_version: Optional[int] = None,
    ) -> Error:
        """Concurrency/version conflict error."""
        details: Dict[str, Any] = {"entity": entity, "identifier": identifier}
        if expected_version is not None:
            details["expected_version"] = expected_version
        if actual_version is not None:
            details["actual_version"] = actual_version
        return Error(
            code="CONCURRENCY_ERROR",
            message=f"Concurrency conflict on {entity}[{identifier}]",
            severity=ErrorSeverity.WARNING,
            details=details,
        )

    @staticmethod
    def internal(
        message: str,
        exception_type: Optional[str] = None,
    ) -> Error:
        """Internal/unexpected error."""
        details: Dict[str, Any] = {}
        if exception_type:
            details["exception_type"] = exception_type
        return Error(
            code="INTERNAL_ERROR",
            message=message,
            severity=ErrorSeverity.ERROR,
            details=details,
        )

    @staticmethod
    def cancelled(
        operation: str,
        reason: Optional[str] = None,
    ) -> Error:
        """Operation cancelled error."""
        return Error(
            code="CANCELLED",
            message=f"Operation '{operation}' was cancelled" + (f": {reason}" if reason else ""),
            severity=ErrorSeverity.INFO,
            details={"operation": operation},
        )

    @staticmethod
    def from_exception(
        exception: Exception,
        code: str = "EXCEPTION",
        source: Optional[str] = None,
    ) -> Error:
        """Create error from exception."""
        return Error(
            code=code,
            message=str(exception),
            severity=ErrorSeverity.ERROR,
            details={"exception_type": type(exception).__name__},
            source=source,
        )


# ============================================================================
# Result Type
# ============================================================================


@dataclass(frozen=True, slots=True)
class Result(Generic[T, E]):
    """
    Result monad for railway-oriented programming.

    Represents either a success with a value or a failure with an error.
    Provides monadic operations for composition without exception handling.

    Usage:
        # Creation
        success = Result.success(42)
        failure = Result.failure(Errors.not_found("User", "123"))

        # Checking
        if result.is_success:
            print(result.value)
        else:
            print(result.error)

        # Unwrapping
        value = result.unwrap()  # Raises if failure
        value = result.unwrap_or(default_value)
        value = result.unwrap_or_else(lambda e: compute_default(e))

        # Chaining (sync)
        result = (
            Result.success(data)
            .map(transform)
            .flat_map(validate)
            .map_error(enrich_error)
        )

        # Chaining (async)
        result = await async_flat_map(result, async_operation)
    """

    _value: Optional[T] = field(default=None)
    _error: Optional[E] = field(default=None)
    _is_success: bool = field(default=True)

    # ========================================================================
    # Factory Methods
    # ========================================================================

    @classmethod
    def success(cls, value: T) -> "Result[T, Any]":
        """Create a successful result."""
        return cls(_value=value, _error=None, _is_success=True)

    @classmethod
    def failure(cls, error: E) -> "Result[Any, E]":
        """Create a failed result."""
        return cls(_value=None, _error=error, _is_success=False)

    @classmethod
    def from_optional(
        cls,
        value: Optional[T],
        error: E,
    ) -> "Result[T, E]":
        """Create result from optional, using error if None."""
        if value is not None:
            return cls.success(value)
        return cls.failure(error)

    @classmethod
    def from_exception(
        cls,
        exception: Exception,
        code: str = "EXCEPTION",
        source: Optional[str] = None,
    ) -> "Result[Any, Error]":
        """Create failure result from exception."""
        error = Error(
            code=code,
            message=str(exception),
            severity=ErrorSeverity.ERROR,
            details={"exception_type": type(exception).__name__},
            source=source,
        )
        return cls.failure(error)

    @classmethod
    def try_execute(
        cls,
        func: Callable[[], T],
        error_code: str = "EXECUTION_ERROR",
    ) -> "Result[T, Error]":
        """Execute function and wrap result/exception."""
        try:
            return cls.success(func())
        except Exception as e:
            return cls.from_exception(e, error_code)

    # ========================================================================
    # Properties
    # ========================================================================

    @property
    def is_success(self) -> bool:
        """Check if result is successful."""
        return self._is_success

    @property
    def is_failure(self) -> bool:
        """Check if result is a failure."""
        return not self._is_success

    @property
    def value(self) -> T:
        """
        Get the success value.

        Raises:
            ValueError: If result is a failure
        """
        if not self._is_success:
            raise ValueError(f"Cannot get value from failure: {self._error}")
        return self._value  # type: ignore

    @property
    def error(self) -> E:
        """
        Get the error.

        Raises:
            ValueError: If result is successful
        """
        if self._is_success:
            raise ValueError("Cannot get error from success")
        return self._error  # type: ignore

    # ========================================================================
    # Unwrapping
    # ========================================================================

    def unwrap(self) -> T:
        """
        Unwrap the value, raising if failure.

        Alias for .value property.
        """
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get value or return default if failure."""
        return self._value if self._is_success else default  # type: ignore

    def unwrap_or_else(self, func: Callable[[E], T]) -> T:
        """Get value or compute default from error."""
        if self._is_success:
            return self._value  # type: ignore
        return func(self._error)  # type: ignore

    def unwrap_error(self) -> E:
        """
        Unwrap the error, raising if success.

        Alias for .error property.
        """
        return self.error

    def to_optional(self) -> Optional[T]:
        """Convert to Optional (None if failure)."""
        return self._value if self._is_success else None

    def to_tuple(self) -> Tuple[Optional[T], Optional[E]]:
        """Convert to (value, error) tuple."""
        return (self._value, self._error)

    # ========================================================================
    # Monadic Operations (Sync)
    # ========================================================================

    def map(self, func: Callable[[T], U]) -> "Result[U, E]":
        """
        Apply function to value if success.

        If failure, returns failure unchanged.
        """
        if self._is_success:
            try:
                return Result.success(func(self._value))  # type: ignore
            except Exception as e:
                return Result.from_exception(e)  # type: ignore
        return Result.failure(self._error)  # type: ignore

    def map_error(self, func: Callable[[E], F]) -> "Result[T, F]":
        """
        Apply function to error if failure.

        If success, returns success unchanged.
        """
        if self._is_success:
            return Result.success(self._value)  # type: ignore
        return Result.failure(func(self._error))  # type: ignore

    def flat_map(self, func: Callable[[T], "Result[U, E]"]) -> "Result[U, E]":
        """
        Apply function returning Result to value if success.

        Also known as bind, chain, or and_then.
        """
        if self._is_success:
            try:
                return func(self._value)  # type: ignore
            except Exception as e:
                return Result.from_exception(e)  # type: ignore
        return Result.failure(self._error)  # type: ignore

    def recover(self, func: Callable[[E], T]) -> "Result[T, E]":
        """
        Recover from failure by computing a success value.
        """
        if self._is_success:
            return self
        try:
            return Result.success(func(self._error))  # type: ignore
        except Exception as e:
            return Result.from_exception(e)  # type: ignore

    def recover_with(self, func: Callable[[E], "Result[T, E]"]) -> "Result[T, E]":
        """
        Recover from failure with another Result.
        """
        if self._is_success:
            return self
        try:
            return func(self._error)  # type: ignore
        except Exception as e:
            return Result.from_exception(e)  # type: ignore

    # ========================================================================
    # Side Effects
    # ========================================================================

    def on_success(self, func: Callable[[T], None]) -> "Result[T, E]":
        """Execute function on success value (for side effects)."""
        if self._is_success:
            func(self._value)  # type: ignore
        return self

    def on_failure(self, func: Callable[[E], None]) -> "Result[T, E]":
        """Execute function on error (for side effects)."""
        if not self._is_success:
            func(self._error)  # type: ignore
        return self

    def on_both(
        self,
        on_success: Callable[[T], None],
        on_failure: Callable[[E], None],
    ) -> "Result[T, E]":
        """Execute appropriate function based on result."""
        if self._is_success:
            on_success(self._value)  # type: ignore
        else:
            on_failure(self._error)  # type: ignore
        return self

    # ========================================================================
    # Matching
    # ========================================================================

    def match(
        self,
        on_success: Callable[[T], U],
        on_failure: Callable[[E], U],
    ) -> U:
        """Pattern match on result, returning a value."""
        if self._is_success:
            return on_success(self._value)  # type: ignore
        return on_failure(self._error)  # type: ignore

    # ========================================================================
    # Conversion
    # ========================================================================

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        if self._is_success:
            return {
                "success": True,
                "value": self._value,
            }
        error_dict = self._error
        if hasattr(self._error, "to_dict"):
            error_dict = self._error.to_dict()  # type: ignore
        return {
            "success": False,
            "error": error_dict,
        }

    # ========================================================================
    # Magic Methods
    # ========================================================================

    def __bool__(self) -> bool:
        """Result is truthy if successful."""
        return self._is_success

    def __repr__(self) -> str:
        if self._is_success:
            return f"Success({self._value!r})"
        return f"Failure({self._error!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Result):
            return NotImplemented
        if self._is_success != other._is_success:
            return False
        if self._is_success:
            return self._value == other._value
        return self._error == other._error

    def __hash__(self) -> int:
        if self._is_success:
            return hash(("success", self._value))
        return hash(("failure", self._error))


# ============================================================================
# Async Operations
# ============================================================================


async def async_map(
    result: Result[T, E],
    func: Callable[[T], Awaitable[U]],
) -> Result[U, E]:
    """
    Async version of map.

    Apply async function to value if success.
    """
    if result.is_success:
        try:
            value = await func(result.value)
            return Result.success(value)
        except Exception as e:
            return Result.from_exception(e)  # type: ignore
    return Result.failure(result.error)


async def async_flat_map(
    result: Result[T, E],
    func: Callable[[T], Awaitable[Result[U, E]]],
) -> Result[U, E]:
    """
    Async version of flat_map.

    Apply async function returning Result to value if success.
    """
    if result.is_success:
        try:
            return await func(result.value)
        except Exception as e:
            return Result.from_exception(e)  # type: ignore
    return Result.failure(result.error)


async def async_recover(
    result: Result[T, E],
    func: Callable[[E], Awaitable[T]],
) -> Result[T, E]:
    """
    Async version of recover.

    Recover from failure by computing a success value asynchronously.
    """
    if result.is_success:
        return result
    try:
        value = await func(result.error)
        return Result.success(value)
    except Exception as e:
        return Result.from_exception(e)  # type: ignore


async def async_try_execute(
    func: Callable[[], Awaitable[T]],
    error_code: str = "ASYNC_EXECUTION_ERROR",
) -> Result[T, Error]:
    """Execute async function and wrap result/exception."""
    try:
        value = await func()
        return Result.success(value)
    except Exception as e:
        return Result.from_exception(e, error_code)


# ============================================================================
# Collection Operations
# ============================================================================


def collect_results(results: List[Result[T, E]]) -> Result[List[T], List[E]]:
    """
    Collect list of results into a result of list.

    If all succeed, returns Success with list of values.
    If any fail, returns Failure with list of all errors.
    """
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


def collect_results_partial(
    results: List[Result[T, E]],
) -> Tuple[List[T], List[E]]:
    """
    Collect results, returning both successes and failures.

    Returns (successes, failures) tuple.
    """
    successes: List[T] = []
    failures: List[E] = []

    for r in results:
        if r.is_success:
            successes.append(r.value)
        else:
            failures.append(r.error)

    return (successes, failures)


def first_success(results: Iterator[Result[T, E]]) -> Result[T, List[E]]:
    """
    Return first successful result or all errors.

    Useful for fallback chains.
    """
    errors: List[E] = []

    for r in results:
        if r.is_success:
            return Result.success(r.value)
        errors.append(r.error)

    return Result.failure(errors)


def sequence_results(
    results: List[Result[T, E]],
) -> Result[List[T], E]:
    """
    Sequence results, stopping at first failure.

    Unlike collect_results, returns first error only.
    """
    values: List[T] = []

    for r in results:
        if r.is_failure:
            return Result.failure(r.error)
        values.append(r.value)

    return Result.success(values)


def partition_results(
    results: List[Result[T, E]],
) -> Tuple[List[Result[T, E]], List[Result[T, E]]]:
    """
    Partition results into (successes, failures).
    """
    successes: List[Result[T, E]] = []
    failures: List[Result[T, E]] = []

    for r in results:
        if r.is_success:
            successes.append(r)
        else:
            failures.append(r)

    return (successes, failures)


# ============================================================================
# Type Aliases
# ============================================================================

# Common result types
ResultE = Result[T, Error]  # Result with Error type
UnitResult = Result[None, Error]  # Result for void operations


# ============================================================================
# Exports
# ============================================================================

__all__ = [
    # Core types
    "Result",
    "Error",
    "Errors",
    "ErrorSeverity",
    # Async operations
    "async_map",
    "async_flat_map",
    "async_recover",
    "async_try_execute",
    # Collection operations
    "collect_results",
    "collect_results_partial",
    "first_success",
    "sequence_results",
    "partition_results",
    # Type aliases
    "ResultE",
    "UnitResult",
]
