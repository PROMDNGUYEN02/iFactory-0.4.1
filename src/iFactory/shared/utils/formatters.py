"""
Shared Formatting Utilities.

Contains pure functions for data parsing and formatting.
These are safe for use across all layers.
"""

from __future__ import annotations
import re
import logging
from datetime import datetime
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)

__all__ = [
    "parse_datetime",
    "format_datetime",
    "format_duration",
    "format_duration_verbose",
    "safe_str",
    "safe_float",
    "safe_int",
]

_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%d/%m/%Y %H:%M:%S",
    "%Y-%m-%d",
)
_MSSQL_FRAC_PATTERN = re.compile("\\.(\\d{7,})")


def parse_datetime(value: Union[str, datetime, None]) -> Optional[datetime]:
    """Safely parse value to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, "to_pydatetime"):
        try:
            return value.to_pydatetime()
        except Exception:
            pass
    if not isinstance(value, str):
        try:
            value = str(value)
        except Exception:
            return None
    value = value.strip()
    if not value or value.lower() in ("none", "null", ""):
        return None

    result = _parse_mssql_format(value)
    if result:
        return result

    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    try:
        if value.endswith("Z"):
            value = value[:-1] + "+00:00"
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        pass
    logger.debug(f"Failed to parse datetime: {value[:50]}")
    return None


def _parse_mssql_format(value: str) -> Optional[datetime]:
    """Parse MSSQL datetime format with 7 decimal places."""
    try:
        if " " not in value:
            return None
        match = _MSSQL_FRAC_PATTERN.search(value)
        if match:
            frac = match.group(1)[:6].ljust(6, "0")
            value = _MSSQL_FRAC_PATTERN.sub(f".{frac}", value)
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f")
        if "." in value:
            parts = value.split(".")
            if len(parts) == 2:
                base_dt = parts[0]
                frac = parts[1][:6].ljust(6, "0")
                return datetime.strptime(f"{base_dt}.{frac}", "%Y-%m-%d %H:%M:%S.%f")
        return datetime.strptime(value, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError, AttributeError):
        return None


def format_datetime(dt: Optional[datetime], fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """Format datetime for display."""
    if not dt:
        return "-"
    if isinstance(dt, str):
        return dt
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)


def format_duration(seconds: float) -> str:
    """Format duration in human-readable format."""
    if not seconds or seconds < 0:
        return "-"
    try:
        secs = int(float(seconds))
    except (ValueError, TypeError):
        return "-"
    (hours, rem) = divmod(secs, 3600)
    (mins, secs) = divmod(rem, 60)
    if hours > 0:
        return f"{hours}h {mins}m"
    if mins > 0:
        return f"{mins}m {secs}s"
    return f"{secs}s"


def format_duration_verbose(seconds: float) -> str:
    """Format duration with full labels."""
    if not seconds or seconds < 0:
        return "0 seconds"
    try:
        total_secs = int(float(seconds))
    except (ValueError, TypeError):
        return "0 seconds"
    (days, rem) = divmod(total_secs, 86400)
    (hours, rem) = divmod(rem, 3600)
    (mins, secs) = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days} day{('s' if days != 1 else '')}")
    if hours > 0:
        parts.append(f"{hours} hour{('s' if hours != 1 else '')}")
    if mins > 0:
        parts.append(f"{mins} minute{('s' if mins != 1 else '')}")
    if secs > 0 or not parts:
        parts.append(f"{secs} second{('s' if secs != 1 else '')}")
    return ", ".join(parts)


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string."""
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    if value is None:
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default
