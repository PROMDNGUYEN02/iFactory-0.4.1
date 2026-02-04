# src/iFactory/domain/exceptions/domain_exceptions.py
"""
Domain-Specific Exceptions.

Contains all domain exceptions organized by domain concept.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Optional

from .base import DomainError, EntityNotFoundError, BusinessRuleViolationError


# ============================================================================
# Equipment/Device Exceptions
# ============================================================================


class InvalidEquipmentCodeError(DomainError):
    """Raised when an equipment code is invalid."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, context, "INVALID_EQUIPMENT_CODE")

    @classmethod
    def empty(cls) -> "InvalidEquipmentCodeError":
        """Code is empty or whitespace only."""
        return cls("Equipment code cannot be empty.")

    @classmethod
    def too_long(cls, code: str, max_length: int) -> "InvalidEquipmentCodeError":
        """Code exceeds maximum length."""
        return cls(
            f"Equipment code '{code}' exceeds maximum length of {max_length}.",
            {"code": code, "max_length": max_length, "actual_length": len(code)},
        )

    @classmethod
    def invalid_format(cls, code: str) -> "InvalidEquipmentCodeError":
        """Code contains invalid characters."""
        return cls(
            f"Invalid equipment code format: '{code}'. " "Expected alphanumeric characters, hyphens, or underscores.",
            {"code": code},
        )

    @classmethod
    def invalid_prefix(cls, code: str, expected_prefixes: list) -> "InvalidEquipmentCodeError":
        """Code has invalid prefix."""
        return cls(
            f"Equipment code '{code}' has invalid prefix. " f"Expected one of: {', '.join(expected_prefixes)}",
            {"code": code, "expected_prefixes": expected_prefixes},
        )


class DeviceNotFoundError(EntityNotFoundError):
    """Raised when a device cannot be found."""

    def __init__(self, code: str) -> None:
        super().__init__("Device", code)

    @classmethod
    def by_code(cls, code: str) -> "DeviceNotFoundError":
        """Factory method for clarity."""
        return cls(code)


# ============================================================================
# Status Transition Exceptions
# ============================================================================


class InvalidStatusTransitionError(BusinessRuleViolationError):
    """Raised when a status transition violates business rules."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            rule="StatusTransition",
            message=message,
            context=context,
        )

    @classmethod
    def illegal_transition(
        cls,
        from_status: str,
        to_status: str,
    ) -> "InvalidStatusTransitionError":
        """Direct transition not allowed."""
        return cls(
            f"Cannot transition directly from '{from_status}' to '{to_status}'.",
            {"from_status": from_status, "to_status": to_status},
        )

    @classmethod
    def requires_intermediate(
        cls,
        from_status: str,
        to_status: str,
        intermediate: str,
    ) -> "InvalidStatusTransitionError":
        """Transition requires intermediate state."""
        return cls(
            f"Transition from '{from_status}' to '{to_status}' requires " f"going through '{intermediate}' first.",
            {
                "from_status": from_status,
                "to_status": to_status,
                "required_intermediate": intermediate,
            },
        )


# Alias for backward compatibility
InvalidTransitionError = InvalidStatusTransitionError


# ============================================================================
# Data Staleness Exceptions
# ============================================================================


class StaleDataError(DomainError):
    """Raised when an operation is attempted with outdated information."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, context, "STALE_DATA")

    @classmethod
    def timestamp_regression(
        cls,
        current: datetime,
        proposed: datetime,
    ) -> "StaleDataError":
        """Proposed timestamp is older than current."""
        return cls(
            f"Cannot update state with past timestamp. " f"Current: {current.isoformat()}, Proposed: {proposed.isoformat()}",
            {
                "current_timestamp": current.isoformat(),
                "proposed_timestamp": proposed.isoformat(),
                "difference_seconds": (current - proposed).total_seconds(),
            },
        )

    @classmethod
    def version_mismatch(
        cls,
        expected: int,
        actual: int,
    ) -> "StaleDataError":
        """Version doesn't match expected."""
        return cls(
            f"Version mismatch: expected {expected}, got {actual}",
            {"expected_version": expected, "actual_version": actual},
        )


# ============================================================================
# Time Range Exceptions
# ============================================================================


class InvalidTimeRangeError(DomainError):
    """Raised when a time range is invalid."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, context, "INVALID_TIME_RANGE")

    @classmethod
    def end_before_start(
        cls,
        start: datetime,
        end: datetime,
    ) -> "InvalidTimeRangeError":
        """End time is before start time."""
        return cls(
            f"Start time ({start.isoformat()}) cannot be after end time ({end.isoformat()}).",
            {
                "start": start.isoformat(),
                "end": end.isoformat(),
            },
        )

    @classmethod
    def non_contiguous(cls) -> "InvalidTimeRangeError":
        """Ranges don't touch or overlap."""
        return cls("Cannot union non-contiguous or non-overlapping time ranges.")

    @classmethod
    def zero_duration(cls) -> "InvalidTimeRangeError":
        """Range has zero duration."""
        return cls("Time range cannot have zero duration.")


# ============================================================================
# Status Period Exceptions
# ============================================================================


class StatusMergeError(DomainError):
    """Raised when status periods cannot be merged."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, context, "STATUS_MERGE_ERROR")

    @classmethod
    def different_devices(cls, code1: str, code2: str) -> "StatusMergeError":
        """Periods belong to different devices."""
        return cls(
            f"Cannot merge periods for different devices: '{code1}' and '{code2}'.",
            {"device_1": code1, "device_2": code2},
        )

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> "StatusMergeError":
        """Periods have different statuses."""
        return cls(
            f"Cannot merge periods with different statuses: '{status1}' and '{status2}'.",
            {"status_1": status1, "status_2": status2},
        )

    @classmethod
    def non_adjacent(cls) -> "StatusMergeError":
        """Periods don't touch."""
        return cls("Cannot merge time ranges that are not adjacent or overlapping.")


# ============================================================================
# Material Exceptions
# ============================================================================


class InvalidMaterialError(DomainError):
    """Raised when material data is invalid."""

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message, context, "INVALID_MATERIAL")

    @classmethod
    def empty_lot_number(cls) -> "InvalidMaterialError":
        """Lot number is empty."""
        return cls("Material lot number cannot be empty.")

    @classmethod
    def invalid_quantity(cls, quantity: float) -> "InvalidMaterialError":
        """Quantity is invalid."""
        return cls(
            f"Invalid material quantity: {quantity}. Must be positive.",
            {"quantity": quantity},
        )


__all__ = [
    # Equipment
    "InvalidEquipmentCodeError",
    "DeviceNotFoundError",
    # Status
    "InvalidStatusTransitionError",
    "InvalidTransitionError",  # Alias
    # Data
    "StaleDataError",
    # Time
    "InvalidTimeRangeError",
    "StatusMergeError",
    # Material
    "InvalidMaterialError",
]
