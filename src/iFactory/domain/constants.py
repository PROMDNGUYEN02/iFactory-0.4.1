"""
Domain Constants and Business Limits.
Pure business constraints with no infrastructure dependencies.
"""

from typing import Final


class DeviceLimits:
    MAX_DEVICES_PER_FACILITY: Final[int] = 1000
    MAX_EQUIPMENT_CODE_LENGTH: Final[int] = 50
    MIN_EQUIPMENT_CODE_LENGTH: Final[int] = 1


class HistoryLimits:
    MAX_STATUS_HISTORY_ROWS: Final[int] = 10000
    MAX_QUERY_DAYS: Final[int] = 365
    DEFAULT_HISTORY_DAYS: Final[int] = 7


class TimingConstraints:
    MIN_STATUS_DURATION_SECONDS: Final[int] = 1
    MAX_GAP_TOLERANCE_SECONDS: Final[int] = 60
    POLL_FAST_MS: Final[int] = 3000
    POLL_SLOW_MS: Final[int] = 5000
    CACHE_TTL_SECONDS: Final[int] = 60


class ApplicationLimits:
    """Backward compatibility alias."""

    MAX_DEVICES: Final[int] = DeviceLimits.MAX_DEVICES_PER_FACILITY
    MAX_HISTORY_ROWS: Final[int] = HistoryLimits.MAX_STATUS_HISTORY_ROWS
    CHUNK_SIZE: Final[int] = 1000
    POLL_FAST_MS: Final[int] = TimingConstraints.POLL_FAST_MS
    POLL_SLOW_MS: Final[int] = TimingConstraints.POLL_SLOW_MS
