from __future__ import annotations
from datetime import datetime
from typing import Any


class DomainError(Exception):
    """Base exception for all domain-level errors."""

    __slots__ = ("message", "details", "code")

    def __init__(self, message: str, details: dict[str, Any] | None = None, code: str | None = None) -> None:
        self.message = message
        self.details = details or {}
        self.code = code or self.__class__.__name__
        super().__init__(self.message)


class DeviceError(DomainError):
    pass


class InvalidEquipmentCodeError(DomainError):
    def __init__(self, code: str, reason: str = "") -> None:
        super().__init__(f"Invalid equipment code: {code} - {reason}", details={"code": code, "reason": reason})

    @classmethod
    def empty(cls) -> InvalidEquipmentCodeError:
        return cls("", "Equipment code cannot be empty.")

    @classmethod
    def invalid_format(cls, code: str) -> InvalidEquipmentCodeError:
        return cls(code, "Expected 2-4 uppercase letters optionally followed by numbers.")


class InvalidTimeRangeError(DomainError):
    def __init__(self, message: str, start: datetime | None = None, end: datetime | None = None) -> None:
        details = {}
        if start:
            details["start"] = start.isoformat()
        if end:
            details["end"] = end.isoformat()
        super().__init__(message, details=details)

    @classmethod
    def end_before_start(cls, start: datetime, end: datetime) -> InvalidTimeRangeError:
        return cls(f"Start time ({start}) cannot be after end time ({end}).", start=start, end=end)


class StatusMergeError(DomainError):
    @classmethod
    def different_devices(cls, code1: str, code2: str) -> StatusMergeError:
        return cls(f"Cannot merge statuses for different devices: {code1} and {code2}.")

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> StatusMergeError:
        return cls(f"Cannot merge different statuses: {status1} and {status2}.")

    @classmethod
    def non_adjacent(cls) -> StatusMergeError:
        return cls("Cannot merge non-adjacent or non-overlapping time ranges.")


class ValidationError(DomainError):
    @classmethod
    def required_field(cls, field: str) -> ValidationError:
        return cls(f"Field is required: {field}", details={"field": field})
