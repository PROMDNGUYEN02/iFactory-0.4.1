from __future__ import annotations
from datetime import datetime
from .base import DomainError


class InvalidTimeRangeError(DomainError):
    @classmethod
    def end_before_start(cls, start: datetime, end: datetime) -> InvalidTimeRangeError:
        return cls(f"Start time ({start}) cannot be after end time ({end}).")

    @classmethod
    def non_contiguous(cls) -> InvalidTimeRangeError:
        return cls("Cannot union non-contiguous or non-overlapping time ranges.")


class StatusMergeError(DomainError):
    @classmethod
    def different_devices(cls, code1: str, code2: str) -> StatusMergeError:
        return cls(f"Cannot merge periods for different devices: {code1} and {code2}.")

    @classmethod
    def different_statuses(cls, status1: str, status2: str) -> StatusMergeError:
        return cls(f"Cannot merge periods of different statuses: {status1} and {status2}.")

    @classmethod
    def non_adjacent(cls) -> StatusMergeError:
        return cls("Cannot merge time ranges that are not adjacent or overlapping.")
