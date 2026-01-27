from __future__ import annotations

from datetime import datetime

from .base import DomainError


class InvalidTimeRangeError(DomainError):
    """Raised when a time range violates business constraints."""

    @classmethod
    def end_before_start(
        cls,
        start: datetime,
        end: datetime,
    ) -> InvalidTimeRangeError:
        return cls(
            f"Start time ({start}) cannot be after end time ({end}).",
            {"start": start.isoformat(), "end": end.isoformat()},
        )

    @classmethod
    def non_contiguous(cls) -> InvalidTimeRangeError:
        return cls("Cannot union non-contiguous or non-overlapping time ranges.")


class StatusMergeError(DomainError):
    """Raised when status periods cannot be merged."""

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
