"""Application configuration constants."""

from typing import Final


class CacheKeys:
    """Cache key constants and helper methods."""

    PREFIX_STATUS: Final[str] = "status"
    PREFIX_GANTT: Final[str] = "gantt"

    @staticmethod
    def device_status(code: str) -> str:
        """Generate cache key for device status."""
        if not code:
            raise ValueError("Equipment code cannot be empty")
        return f"{CacheKeys.PREFIX_STATUS}:{code}"

    @staticmethod
    def gantt_segments(code: str, date_str: str) -> str:
        """Generate cache key for gantt segments."""
        if not code:
            raise ValueError("Equipment code cannot be empty")
        return f"{CacheKeys.PREFIX_GANTT}:{code}:{date_str}"


class CacheDefaults:
    """Default cache TTL values in seconds."""

    TTL_STATUS: Final[float] = 30.0
    TTL_GANTT: Final[float] = 60.0
    TTL_DEVICE_LIST: Final[float] = 300.0
