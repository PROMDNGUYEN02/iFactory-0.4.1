"""
Status Normalization Domain Service.

Contains business logic for normalizing status values from various sources.
This logic was previously scattered across layers (enum, presentation).
"""

from __future__ import annotations

from ..enums.device_status import DeviceStatus

__all__ = ["StatusNormalizationService"]


class StatusNormalizationService:
    """
    Domain Service for status normalization.

    Trách nhiệm:
        - Normalize status từ các format khác nhau (code, name, alias)
        - Cung cấp single source of truth cho normalization
        - Không chứa UI concerns (colors, emojis)

    Business Rules:
        - Các alias maps đến chuẩn DeviceStatus enums
        - Default fallback là UNKNOWN khi không match
    """

    _NORMALIZATION_MAP = {
        # Primary names
        "unknown": DeviceStatus.UNKNOWN,
        "running": DeviceStatus.RUNNING,
        "shutdown": DeviceStatus.SHUTDOWN,
        "stop": DeviceStatus.STOP,
        "maintenance": DeviceStatus.MAINTENANCE,
        "alarm": DeviceStatus.ALARM,
        # Common aliases
        "run": DeviceStatus.RUNNING,
        "active": DeviceStatus.RUNNING,
        "on": DeviceStatus.RUNNING,
        "off": DeviceStatus.SHUTDOWN,
        "shut": DeviceStatus.SHUTDOWN,
        "stopped": DeviceStatus.STOP,
        "idle": DeviceStatus.STOP,
        "maint": DeviceStatus.MAINTENANCE,
        "pm": DeviceStatus.MAINTENANCE,
        "error": DeviceStatus.ALARM,
        "fault": DeviceStatus.ALARM,
        "warning": DeviceStatus.ALARM,
        "none": DeviceStatus.UNKNOWN,
        "null": DeviceStatus.UNKNOWN,
        "n/a": DeviceStatus.UNKNOWN,
        "": DeviceStatus.UNKNOWN,
    }

    @classmethod
    def normalize(cls, value: str | None) -> DeviceStatus:
        """
        Normalize any status input to DeviceStatus enum.

        Args:
            value: Status value (code, name, alias, or None)

        Returns:
            Normalized DeviceStatus enum member
        """
        if value is None:
            return DeviceStatus.UNKNOWN
        clean = str(value).strip().lower()
        return cls._NORMALIZATION_MAP.get(clean, DeviceStatus.UNKNOWN)

    @classmethod
    def try_normalize(cls, value: str | None) -> DeviceStatus | None:
        """
        Try to normalize without falling back to UNKNOWN.

        Args:
            value: Status value to normalize

        Returns:
            DeviceStatus if found, None otherwise
        """
        if value is None:
            return None
        clean = str(value).strip().lower()
        if not clean:
            return None
        return cls._NORMALIZATION_MAP.get(clean)

    @classmethod
    def is_valid(cls, value: str | None) -> bool:
        """
        Check if a value can be normalized to a valid status.

        Args:
            value: Status value to check

        Returns:
            True if value can be normalized to a known status
        """
        if value is None:
            return False
        clean = str(value).strip().lower()
        if not clean:
            return False
        return clean in cls._NORMALIZATION_MAP

    @classmethod
    def get_all_aliases(cls) -> dict[str, str]:
        """
        Get all normalization aliases.

        Returns:
            Dictionary mapping alias to status name (for debugging)
        """
        return {alias: status.name for alias, status in cls._NORMALIZATION_MAP.items()}

    @classmethod
    def get_aliases_for_status(cls, status: DeviceStatus) -> list[str]:
        """
        Get all aliases for a specific status.

        Args:
            status: The DeviceStatus enum member

        Returns:
            List of all aliases that normalize to this status
        """
        return [alias for alias, s in cls._NORMALIZATION_MAP.items() if s == status]
