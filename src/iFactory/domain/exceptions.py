from __future__ import annotations
from datetime import datetime
from typing import Any, Optional


class DomainError(Exception):
    """Base exception for all domain-level business rule violations."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)


class InvalidEquipmentCodeError(DomainError):
    @classmethod
    def empty(cls) -> InvalidEquipmentCodeError:
        return cls("Equipment code cannot be empty.")

    @classmethod
    def invalid_format(cls, code: str) -> InvalidEquipmentCodeError:
        return cls(f"Invalid equipment code format: '{code}'. Expected 2-4 uppercase letters optionally followed by numbers.", {"code": code})


class InvalidTimeRangeError(DomainError):
    @classmethod
    def end_before_start(cls, start: datetime, end: datetime) -> InvalidTimeRangeError:
        return cls(f"Start time ({start}) cannot be after end time ({end}).", {"start": start, "end": end})

    @classmethod
    def non_contiguous(cls) -> InvalidTimeRangeError:
        return cls("Cannot union non-contiguous or non-overlapping time ranges.")


class StatusMergeError(DomainError):
    @classmethod
    def different_devices(cls, code1: str, code2: str) -> StatusMergeError:
        return cls(f"Cannot merge status periods for different devices: {code1} and {code2}.")

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> StatusMergeError:
        return cls(f"Cannot merge contiguous periods of different statuses: {status1} and {status2}.")

    @classmethod
    def non_adjacent(cls) -> StatusMergeError:
        return cls("Cannot merge time ranges that are not adjacent or overlapping.")


class InvalidStatusTransitionError(DomainError):
    @classmethod
    def illegal_transition(cls, from_status: str, to_status: str) -> InvalidStatusTransitionError:
        return cls(f"Illegal machine status transition from '{from_status}' to '{to_status}'.", {"from": from_status, "to": to_status})
