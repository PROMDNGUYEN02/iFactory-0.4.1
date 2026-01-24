"""
Domain Exceptions - Business Logic Error Hierarchy.

All custom exceptions inherit from DomainError, providing:
    - Structured error messages.
    - Error codes for logging/API handling.
    - Detail dictionaries for context.
    - Factory methods for common scenarios.
"""

from __future__ import annotations
from datetime import datetime
from typing import Any

__all__ = [
    "DomainError",
    "DeviceError",
    "DeviceNotFoundError",
    "InvalidStatusError",
    "InvalidDeviceStateError",
    "InvalidEquipmentCodeError",
    "InvalidTimeRangeError",
    "HistoryMergeError",
    "ValidationError",
    "RepositoryError",
]


class DomainError(Exception):
    """
    Base exception for all domain-related errors.

    Provides a structured way to handle errors within the business logic,
    including an error code, message, and optional details dictionary.
    """

    __slots__ = ("message", "details", "code")

    def __init__(
        self,
        message: str = "A domain error occurred",
        details: dict[str, Any] | None = None,
        code: str | None = None,
    ) -> None:
        self.message = message
        self.details = details or {}
        self.code = code or self.__class__.__name__
        super().__init__(self.message)

    def __str__(self) -> str:
        if self.details:
            return f"[{self.code}] {self.message} | {self.details}"
        return f"[{self.code}] {self.message}"

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(message={self.message!r}, code={self.code!r})"

    def to_dict(self) -> dict[str, Any]:
        """Convert exception to dictionary for serialization."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


class DeviceError(DomainError):
    """Base exception for all device-related errors."""

    pass


class DeviceNotFoundError(DeviceError):
    """Raised when a device lookup fails (e.g., by ID or Code)."""

    def __init__(self, device_id: str) -> None:
        super().__init__(
            f"Device not found: {device_id}",
            details={"device_id": device_id},
        )
        self.device_id = device_id

    @classmethod
    def by_code(cls, code: str) -> "DeviceNotFoundError":
        """Factory for lookup by equipment code."""
        return cls(code)

    @classmethod
    def by_codes(cls, codes: list[str]) -> "DeviceNotFoundError":
        """Factory for lookup by multiple equipment codes."""
        return cls(f"[{', '.join(codes)}]")


class InvalidStatusError(DeviceError):
    """Raised when a status value is invalid or cannot be normalized."""

    def __init__(self, status: Any, device_id: str | None = None) -> None:
        details: dict[str, Any] = {"status": str(status)}
        if device_id:
            details["device_id"] = device_id
        super().__init__(f"Invalid status: {status}", details=details)
        self.status = status
        self.device_id = device_id

    @classmethod
    def unrecognized(cls, value: str) -> "InvalidStatusError":
        """Factory for unrecognized status codes."""
        return cls(value)

    @classmethod
    def for_device(cls, status: str, device_id: str) -> "InvalidStatusError":
        """Factory with device context."""
        return cls(status, device_id)


class InvalidDeviceStateError(DeviceError):
    """Raised when an operation is invalid for the current device state."""

    def __init__(
        self,
        message: str,
        device_id: str | None = None,
        current_state: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if device_id:
            details["device_id"] = device_id
        if current_state:
            details["current_state"] = current_state
        super().__init__(message, details=details)
        self.device_id = device_id
        self.current_state = current_state

    @classmethod
    def cannot_transition(cls, device_id: str, from_status: str, to_status: str) -> "InvalidDeviceStateError":
        """Factory for invalid status transitions."""
        return cls(
            f"Cannot transition from '{from_status}' to '{to_status}'",
            device_id=device_id,
            current_state=from_status,
        )

    @classmethod
    def already_in_state(cls, device_id: str, state: str) -> "InvalidDeviceStateError":
        """Factory for attempting to enter current state."""
        return cls(
            f"Device is already in '{state}' state",
            device_id=device_id,
            current_state=state,
        )


class InvalidEquipmentCodeError(DomainError):
    """Raised when an equipment code fails validation rules."""

    def __init__(self, code: str, reason: str = "") -> None:
        message = f"Invalid equipment code: {code}"
        if reason:
            message += f" - {reason}"
        super().__init__(message, details={"code": code, "reason": reason})
        self.invalid_code = code
        self.reason = reason

    @classmethod
    def empty(cls) -> "InvalidEquipmentCodeError":
        """Factory for empty code."""
        return cls("", "Equipment code cannot be empty")

    @classmethod
    def too_short(cls, code: str) -> "InvalidEquipmentCodeError":
        """Factory for code that is too short."""
        return cls(code, "Minimum 2 characters required")

    @classmethod
    def too_long(cls, code: str) -> "InvalidEquipmentCodeError":
        """Factory for code that is too long."""
        return cls(code, "Maximum 10 characters allowed")

    @classmethod
    def invalid_format(cls, code: str) -> "InvalidEquipmentCodeError":
        """Factory for pattern mismatch."""
        return cls(
            code,
            "Expected 2-4 uppercase letters optionally followed by alphanumerics. " "Examples: CA, CA1, CA111, CCT, CCT01, CBC02",
        )

    @classmethod
    def none_provided(cls) -> "InvalidEquipmentCodeError":
        """Factory for None value."""
        return cls("None", "Equipment code cannot be None")


class InvalidTimeRangeError(DomainError):
    """Raised when a time range is logically invalid."""

    def __init__(
        self,
        message: str,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if start is not None:
            details["start"] = start.isoformat()
        if end is not None:
            details["end"] = end.isoformat()
        super().__init__(message, details=details)
        self.start = start
        self.end = end

    @classmethod
    def end_before_start(cls, start: datetime, end: datetime) -> "InvalidTimeRangeError":
        """Factory for reversed time boundaries."""
        return cls(
            f"Start time ({start}) cannot be after end time ({end})",
            start=start,
            end=end,
        )

    @classmethod
    def null_boundary(cls, which: str) -> "InvalidTimeRangeError":
        """Factory for null start or end."""
        return cls(f"Time range {which} cannot be None")

    @classmethod
    def negative_duration(cls, seconds: float) -> "InvalidTimeRangeError":
        """Factory for negative duration."""
        return cls(f"Duration cannot be negative: {seconds}s")

    @classmethod
    def zero_duration(cls) -> "InvalidTimeRangeError":
        """Factory for zero duration when not allowed."""
        return cls("Time range must have positive duration")


class HistoryMergeError(DomainError):
    """Raised when two history periods cannot be merged."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message, details=details)

    @classmethod
    def different_devices(cls, code1: str, code2: str) -> "HistoryMergeError":
        """Factory for mismatched device codes."""
        return cls(
            "Cannot merge history periods from different devices",
            details={"device1": code1, "device2": code2},
        )

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> "HistoryMergeError":
        """Factory for mismatched statuses."""
        return cls(
            "Cannot merge history periods with different statuses",
            details={"status1": status1, "status2": status2},
        )

    @classmethod
    def non_adjacent(cls, gap_seconds: float) -> "HistoryMergeError":
        """Factory for non-adjacent periods."""
        return cls(
            "Cannot merge non-adjacent history periods",
            details={"gap_seconds": gap_seconds},
        )

    @classmethod
    def overlapping(cls, overlap_seconds: float) -> "HistoryMergeError":
        """Factory for overlapping periods that shouldn't be merged."""
        return cls(
            "Cannot merge overlapping history periods",
            details={"overlap_seconds": overlap_seconds},
        )


class ValidationError(DomainError):
    """Raised when general data validation fails."""

    def __init__(
        self,
        message: str,
        field: str | None = None,
        value: Any | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if field:
            details["field"] = field
        if value is not None:
            details["value"] = str(value)[:100]
        super().__init__(message, details=details if details else None)
        self.field = field
        self.value = value

    @classmethod
    def required_field(cls, field: str) -> "ValidationError":
        """Factory for required field missing."""
        return cls(f"Field '{field}' is required", field=field)

    @classmethod
    def invalid_type(cls, field: str, expected: str, got: str) -> "ValidationError":
        """Factory for type mismatch."""
        return cls(
            f"Field '{field}' expected {expected}, got {got}",
            field=field,
        )


class RepositoryError(DomainError):
    """
    Raised when a repository operation fails.

    Note: This is a domain-level exception for repository contract violations.
    Infrastructure-specific errors (e.g., connection failures) should be
    wrapped in this exception at the repository boundary.
    """

    def __init__(
        self,
        message: str,
        operation: str | None = None,
        entity_type: str | None = None,
    ) -> None:
        details: dict[str, Any] = {}
        if operation:
            details["operation"] = operation
        if entity_type:
            details["entity_type"] = entity_type
        super().__init__(message, details=details)
        self.operation = operation
        self.entity_type = entity_type

    @classmethod
    def save_failed(cls, entity_type: str, reason: str = "") -> "RepositoryError":
        """Factory for save operation failure."""
        msg = f"Failed to save {entity_type}"
        if reason:
            msg += f": {reason}"
        return cls(msg, operation="save", entity_type=entity_type)

    @classmethod
    def query_failed(cls, entity_type: str, reason: str = "") -> "RepositoryError":
        """Factory for query operation failure."""
        msg = f"Failed to query {entity_type}"
        if reason:
            msg += f": {reason}"
        return cls(msg, operation="query", entity_type=entity_type)
