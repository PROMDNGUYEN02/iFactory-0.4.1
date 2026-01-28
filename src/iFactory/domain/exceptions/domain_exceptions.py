from __future__ import annotations

from datetime import datetime
from typing import Any, Dict

from .base import DomainError


# --- Device Exceptions ---


class InvalidEquipmentCodeError(DomainError):
    @classmethod
    def empty(cls) -> InvalidEquipmentCodeError:
        return cls("Equipment code cannot be empty.")

    @classmethod
    def too_long(cls, code: str, max_length: int) -> InvalidEquipmentCodeError:
        return cls(
            f"Equipment code '{code}' exceeds maximum length of {max_length}.",
            {"code": code, "max_length": max_length},
        )

    @classmethod
    def invalid_format(cls, code: str) -> InvalidEquipmentCodeError:
        return cls(
            f"Invalid equipment code format: '{code}'. " "Expected alphanumeric characters, hyphens, or underscores.",
            {"code": code},
        )


class InvalidStatusTransitionError(DomainError):
    @classmethod
    def illegal_transition(
        cls,
        from_status: str,
        to_status: str,
    ) -> InvalidStatusTransitionError:
        return cls(
            f"Illegal status transition from '{from_status}' to '{to_status}'.",
            {"from_status": from_status, "to_status": to_status},
        )


class DeviceNotFoundError(DomainError):
    @classmethod
    def by_code(cls, code: str) -> DeviceNotFoundError:
        return cls(
            f"Device with code '{code}' not found.",
            {"equipment_code": code},
        )


class StaleDataError(DomainError):
    """Raised when an operation is attempted with outdated information."""

    @classmethod
    def timestamp_regression(cls, current: datetime, proposed: datetime) -> StaleDataError:
        return cls(
            f"Cannot update state with past timestamp. " f"Current: {current}, Proposed: {proposed}", {"current_ts": current, "proposed_ts": proposed}
        )


# --- Time & History Exceptions ---


class InvalidTimeRangeError(DomainError):
    @classmethod
    def end_before_start(
        cls,
        start: datetime,
        end: datetime,
    ) -> InvalidTimeRangeError:
        return cls(
            f"Start time ({start}) cannot be after end time ({end}).",
            {"start": start, "end": end},
        )

    @classmethod
    def non_contiguous(cls) -> InvalidTimeRangeError:
        return cls("Cannot union non-contiguous or non-overlapping time ranges.")


class StatusMergeError(DomainError):
    @classmethod
    def different_devices(cls, code1: str, code2: str) -> StatusMergeError:
        return cls(
            f"Cannot merge periods for different devices: {code1} and {code2}.",
            {"device_1": code1, "device_2": code2},
        )

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> StatusMergeError:
        return cls(
            f"Cannot merge periods of different statuses: {status1} and {status2}.",
            {"status_1": status1, "status_2": status2},
        )

    @classmethod
    def non_adjacent(cls) -> StatusMergeError:
        return cls("Cannot merge time ranges that are not adjacent or overlapping.")
