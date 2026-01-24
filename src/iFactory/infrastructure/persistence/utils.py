"""
Persistence layer utilities - Compatibility Wrapper.

This module re-exports utilities from the Shared Kernel to maintain
backward compatibility within the Infrastructure layer without creating
circular dependencies with the Application layer.
"""

# Re-export formatters from Shared
from ...shared.utils.formatters import (
    parse_datetime,
    format_datetime,
    format_duration,
    format_duration_verbose,
    safe_str,
    safe_float,
    safe_int,
)

# Re-export file helpers from Shared
from ...shared.utils.file_helpers import (
    LayoutCache,
    load_layout,
    extract_codes_from_layout,
    get_data_directory,
)

__all__ = [
    # Formatters
    "parse_datetime",
    "format_datetime",
    "format_duration",
    "format_duration_verbose",
    "safe_str",
    "safe_float",
    "safe_int",
    # File Helpers
    "LayoutCache",
    "load_layout",
    "extract_codes_from_layout",
    "get_data_directory",
]
