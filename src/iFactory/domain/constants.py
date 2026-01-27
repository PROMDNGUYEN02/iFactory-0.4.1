"""
Domain: Business Limits and Constraints.
"""

from typing import Final


class ApplicationLimits:
    MAX_DEVICES: Final[int] = 1000
    MAX_HISTORY_ROWS: Final[int] = 10000
    CHUNK_SIZE: Final[int] = 1000


class TimeConstants:
    CACHE_TTL_MS: Final[int] = 30000
    POLL_INTERVAL_MS: Final[int] = 5000
