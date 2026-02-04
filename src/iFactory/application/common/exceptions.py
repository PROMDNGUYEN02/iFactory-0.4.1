# src/iFactory/application/common/exceptions.py
"""
Application Layer Exceptions.

These exceptions are used for application-level errors that should be
handled differently from domain errors.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class ApplicationException(Exception):
    """
    Base exception for all application layer errors.

    Provides structured error information for logging and API responses.
    """

    def __init__(
        self,
        message: str,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self._default_code()
        self.details = details or {}

    def _default_code(self) -> str:
        """Generate default error code from class name."""
        name = self.__class__.__name__
        # Convert CamelCase to SCREAMING_SNAKE_CASE
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).upper()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.message!r}, code={self.code!r})"


# ============================================================================
# Resource Errors
# ============================================================================


class ResourceNotFoundException(ApplicationException):
    """Raised when a requested resource is not found."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        message: Optional[str] = None,
    ) -> None:
        self.resource_type = resource_type
        self.resource_id = resource_id
        super().__init__(
            message=message or f"{resource_type} with ID '{resource_id}' not found",
            code="RESOURCE_NOT_FOUND",
            details={
                "resource_type": resource_type,
                "resource_id": str(resource_id),
            },
        )


class ResourceConflictException(ApplicationException):
    """Raised when there's a conflict with existing resource."""

    def __init__(
        self,
        resource_type: str,
        conflict_reason: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=f"Conflict with {resource_type}: {conflict_reason}",
            code="RESOURCE_CONFLICT",
            details={
                "resource_type": resource_type,
                "reason": conflict_reason,
                **(details or {}),
            },
        )


# ============================================================================
# External Service Errors
# ============================================================================


class RemoteSourceException(ApplicationException):
    """Raised when the remote data source fails."""

    def __init__(
        self,
        source: str,
        message: str,
        original_error: Optional[Exception] = None,
    ) -> None:
        self.source = source
        self.original_error = original_error
        super().__init__(
            message=f"Remote source '{source}' failed: {message}",
            code="REMOTE_SOURCE_ERROR",
            details={
                "source": source,
                "original_error": str(original_error) if original_error else None,
            },
        )


class RemoteSourceUnavailableException(RemoteSourceException):
    """Raised when remote source is not available."""

    def __init__(self, source: str) -> None:
        super().__init__(
            source=source,
            message="Service is currently unavailable",
        )
        self.code = "REMOTE_SOURCE_UNAVAILABLE"


class RemoteSourceTimeoutException(RemoteSourceException):
    """Raised when remote source times out."""

    def __init__(self, source: str, timeout_seconds: float) -> None:
        super().__init__(
            source=source,
            message=f"Request timed out after {timeout_seconds}s",
        )
        self.code = "REMOTE_SOURCE_TIMEOUT"
        self.details["timeout_seconds"] = timeout_seconds


# ============================================================================
# Validation Errors
# ============================================================================


class ValidationException(ApplicationException):
    """Raised when request validation fails."""

    def __init__(
        self,
        message: str,
        validation_errors: Optional[Dict[str, list]] = None,
    ) -> None:
        self.validation_errors = validation_errors or {}
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            details={"errors": self.validation_errors},
        )

    @classmethod
    def from_errors(
        cls,
        errors: Dict[str, list],
    ) -> "ValidationException":
        """Create from validation errors dict."""
        error_count = sum(len(e) for e in errors.values())
        return cls(
            message=f"Validation failed with {error_count} error(s)",
            validation_errors=errors,
        )


# ============================================================================
# Authorization Errors
# ============================================================================


class AuthorizationException(ApplicationException):
    """Raised when user is not authorized for an operation."""

    def __init__(
        self,
        operation: str,
        reason: Optional[str] = None,
    ) -> None:
        self.operation = operation
        super().__init__(
            message=f"Not authorized to perform '{operation}'" + (f": {reason}" if reason else ""),
            code="AUTHORIZATION_ERROR",
            details={"operation": operation},
        )


class AuthenticationException(ApplicationException):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication required") -> None:
        super().__init__(
            message=message,
            code="AUTHENTICATION_ERROR",
        )


# ============================================================================
# Configuration Errors
# ============================================================================


class ConfigurationException(ApplicationException):
    """Raised when there's a configuration error."""

    def __init__(
        self,
        setting: str,
        message: str,
    ) -> None:
        self.setting = setting
        super().__init__(
            message=f"Configuration error for '{setting}': {message}",
            code="CONFIGURATION_ERROR",
            details={"setting": setting},
        )


# ============================================================================
# Concurrency Errors
# ============================================================================


class ConcurrencyException(ApplicationException):
    """Raised when there's a concurrency conflict."""

    def __init__(
        self,
        resource_type: str,
        resource_id: Any,
        message: Optional[str] = None,
    ) -> None:
        super().__init__(
            message=message or f"Concurrency conflict on {resource_type}[{resource_id}]",
            code="CONCURRENCY_ERROR",
            details={
                "resource_type": resource_type,
                "resource_id": str(resource_id),
            },
        )


__all__ = [
    # Base
    "ApplicationException",
    # Resource
    "ResourceNotFoundException",
    "ResourceConflictException",
    # Remote
    "RemoteSourceException",
    "RemoteSourceUnavailableException",
    "RemoteSourceTimeoutException",
    # Validation
    "ValidationException",
    # Authorization
    "AuthorizationException",
    "AuthenticationException",
    # Configuration
    "ConfigurationException",
    # Concurrency
    "ConcurrencyException",
]
