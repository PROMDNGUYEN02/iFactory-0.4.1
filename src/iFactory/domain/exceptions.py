from __future__ import annotations

from datetime import datetime
from typing import Any


class DomainError(Exception):
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


class DeviceError(DomainError):
    pass


class DeviceNotFoundError(DeviceError):
    def __init__(self, device_id: str) -> None:
        super().__init__(f"Device not found: {device_id}", details={"device_id": device_id})


class InvalidStatusError(DeviceError):
    def __init__(self, status: Any, device_id: str | None = None) -> None:
        details: dict[str, Any] = {"status": str(status)}
        if device_id:
            details["device_id"] = device_id
        super().__init__(f"Invalid status: {status}", details=details)


class InvalidDeviceStateError(DeviceError):
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


class InvalidEquipmentCodeError(DomainError):
    def __init__(self, code: str, reason: str = "") -> None:
        super().__init__(f"Invalid equipment code: {code} - {reason}", details={"code": code, "reason": reason})

    @classmethod
    def empty(cls) -> "InvalidEquipmentCodeError":
        return cls("", "Equipment code cannot be empty")

    @classmethod
    def invalid_format(cls, code: str) -> "InvalidEquipmentCodeError":
        return cls(code, "Expected 2-4 uppercase letters optionally followed by alphanumerics")


class InvalidTimeRangeError(DomainError):
    def __init__(self, message: str, start: datetime | None = None, end: datetime | None = None) -> None:
        details = {}
        if start:
            details["start"] = start.isoformat()
        if end:
            details["end"] = end.isoformat()
        super().__init__(message, details=details)

    @classmethod
    def end_before_start(cls, start: datetime, end: datetime) -> "InvalidTimeRangeError":
        return cls(f"Start time ({start}) cannot be after end time ({end})", start=start, end=end)


class HistoryMergeError(DomainError):
    @classmethod
    def different_devices(cls, code1: str, code2: str) -> "HistoryMergeError":
        return cls("Cannot merge history from different devices", details={"device1": code1, "device2": code2})

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> "HistoryMergeError":
        return cls("Cannot merge history with different statuses", details={"status1": status1, "status2": status2})


class ValidationError(DomainError):
    pass


class RepositoryError(DomainError):
    pass
