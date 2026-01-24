"""
Status Normalizer - Centralized Status Code Normalization.

Eliminates duplicated status code extraction and normalization logic
across the entire codebase. Single source of truth for status handling.
"""

from __future__ import annotations
import logging
from collections import NamedTuple
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class NormalizedStatus(NamedTuple):
    """Normalized status representation."""

    code: str
    name: str
    display: str
    color_light: str
    color_dark: str
    category: str = "unknown"

    @property
    def color(self, theme: str = "light") -> str:
        """Get color for theme."""
        return self.color_dark if theme == "dark" else self.color_light


class StatusNormalizer:
    """
    Centralizes status code normalization across the system.

    Eliminates repeated extraction patterns throughout codebase.
    Provides single source of truth for status information.

    Usage:
        ```python
        raw = {"EQUIP_STATUS": 1}
        normalized = StatusNormalizer.normalize(raw)
        # NormalizedStatus(code='1', name='running', display='Running', ...)
        ```
    """

    STATUS_MAP: Dict[str, NormalizedStatus] = {
        "0": NormalizedStatus("0", "unknown", "Unknown", "#9E9E9E", "#757575", "idle"),
        "1": NormalizedStatus("1", "running", "Running", "#4CAF50", "#66BB6A", "active"),
        "2": NormalizedStatus("2", "shutdown", "Shutdown", "#757575", "#616161", "inactive"),
        "3": NormalizedStatus("3", "stop", "Stop", "#F44336", "#EF5350", "error"),
        "4": NormalizedStatus("4", "maintenance", "Maintenance", "#2196F3", "#42A5F5", "maintenance"),
        "5": NormalizedStatus("5", "alarm", "Alarm", "#FF9800", "#FFA726", "warning"),
    }

    NAME_TO_CODE: Dict[str, str] = {
        "unknown": "0",
        "running": "1",
        "shutdown": "2",
        "stop": "3",
        "maintenance": "4",
        "alarm": "5",
    }

    @classmethod
    def normalize(cls, raw_value: Any) -> NormalizedStatus:
        """
        Normalize any status representation to canonical form.

        Accepts:
        - Code: "1", 1
        - Name: "running", "RUNNING"
        - Dict: {"status_code": "1"}, {"EQUIP_STATUS": 1}
        - Object with status_code attribute

        Args:
            raw_value: Any status representation

        Returns:
            NormalizedStatus with canonical information
        """
        code = cls._extract_code(raw_value)
        return cls.STATUS_MAP.get(code, cls.STATUS_MAP["0"])

    @classmethod
    def _extract_code(cls, raw_value: Any) -> str:
        """Extract status code from various formats."""
        if raw_value is None:
            return "0"
        if isinstance(raw_value, int):
            return str(raw_value)
        if isinstance(raw_value, str):
            if raw_value.lower() in cls.NAME_TO_CODE:
                return cls.NAME_TO_CODE[raw_value.lower()]
            return raw_value if raw_value in cls.STATUS_MAP else "0"
        if isinstance(raw_value, dict):
            for key in (
                "status_code",
                "status",
                "EQUIP_STATUS",
                "equip_status",
                "code",
            ):
                if (val := raw_value.get(key)) is not None:
                    if isinstance(val, dict):
                        continue
                    return cls._extract_code(val)
        if hasattr(raw_value, "status_code"):
            return cls._extract_code(raw_value.status_code)
        if hasattr(raw_value, "equip_status"):
            return cls._extract_code(raw_value.equip_status)
        return "0"

    @classmethod
    def get_color(cls, code: str, theme: str = "light") -> str:
        """Get color for status code and theme."""
        status = cls.STATUS_MAP.get(str(code), cls.STATUS_MAP["0"])
        return status.color_dark if theme == "dark" else status.color_light

    @classmethod
    def get_display(cls, code: str) -> str:
        """Get display text for status code."""
        status = cls.STATUS_MAP.get(str(code), cls.STATUS_MAP["0"])
        return status.display

    @classmethod
    def get_category(cls, code: str) -> str:
        """Get category for status code."""
        status = cls.STATUS_MAP.get(str(code), cls.STATUS_MAP["0"])
        return status.category


__all__ = ["StatusNormalizer", "NormalizedStatus"]
