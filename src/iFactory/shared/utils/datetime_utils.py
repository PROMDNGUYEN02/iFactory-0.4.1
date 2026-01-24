"""
Datetime utilities - Shared parsing and formatting functions.
"""
from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Any, Optional, Union
logger = logging.getLogger(__name__)
__all__ = ['parse_datetime', 'format_datetime', 'format_duration', 'safe_str', 'safe_float']
_DATETIME_FORMATS = ('%Y-%m-%d %H:%M:%S.%f', '%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S.%f', '%Y-%m-%dT%H:%M:%S', '%Y/%m/%d %H:%M:%S', '%d/%m/%Y %H:%M:%S', '%Y-%m-%d')
_MSSQL_FRAC_PATTERN = re.compile('\\.(\\d{7,})')

def parse_datetime(value: Union[str, datetime, None]) -> Optional[datetime]:
    """
    Safely parse value to datetime.
    
    Handles:
    - datetime objects (returned as-is)
    - Pandas Timestamp (via to_pydatetime)
    - ISO format strings
    - MSSQL datetime strings with 7 decimal places
    - Common datetime formats
    
    Args:
        value: Value to parse
        
    Returns:
        datetime object or None if parsing fails
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if hasattr(value, 'to_pydatetime'):
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
    if not value or value.lower() in ('none', 'null', ''):
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
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        pass
    logger.debug(f'Failed to parse datetime: {(value[:50] if len(value) > 50 else value)}')
    return None

def _parse_mssql_format(value: str) -> Optional[datetime]:
    """
    Parse MSSQL datetime format.
    
    MSSQL returns datetime like: '2026-01-07 09:17:23.7480000'
    with 7 decimal places for nanoseconds (datetime2).
    Python's strptime only supports 6 decimal places.
    """
    try:
        if ' ' not in value:
            return None
        match = _MSSQL_FRAC_PATTERN.search(value)
        if match:
            frac = match.group(1)[:6].ljust(6, '0')
            value = _MSSQL_FRAC_PATTERN.sub(f'.{frac}', value)
            return datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
        if '.' in value:
            parts = value.split('.')
            if len(parts) == 2:
                base_dt = parts[0]
                frac = parts[1][:6].ljust(6, '0')
                return datetime.strptime(f'{base_dt}.{frac}', '%Y-%m-%d %H:%M:%S.%f')
        return datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError, AttributeError):
        return None

def format_datetime(dt: Optional[datetime], fmt: str='%Y-%m-%d %H:%M:%S') -> str:
    """
    Format datetime for display.
    
    Args:
        dt: Datetime to format
        fmt: Format string
        
    Returns:
        Formatted string or "-" if None
    """
    if not dt:
        return '-'
    if isinstance(dt, str):
        return dt
    try:
        return dt.strftime(fmt)
    except Exception:
        return str(dt)

def format_duration(seconds: float) -> str:
    """
    Format duration in human-readable format.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "2h 30m", "45m 10s", "30s")
    """
    if not seconds or seconds < 0:
        return '-'
    try:
        secs = int(float(seconds))
    except (ValueError, TypeError):
        return '-'
    (hours, rem) = divmod(secs, 3600)
    (mins, secs) = divmod(rem, 60)
    if hours > 0:
        return f'{hours}h {mins}m'
    if mins > 0:
        return f'{mins}m {secs}s'
    return f'{secs}s'

def safe_str(value: Any, default: str='') -> str:
    """
    Safely convert value to string.
    
    Args:
        value: Value to convert
        default: Default if conversion fails
        
    Returns:
        String representation
    """
    if value is None:
        return default
    try:
        return str(value)
    except Exception:
        return default

def safe_float(value: Any, default: float=0.0) -> float:
    """
    Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default if conversion fails
        
    Returns:
        Float value
    """
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default