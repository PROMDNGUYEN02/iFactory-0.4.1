"""Shared Core module - Cross-cutting utilities."""

from .result import (
    Result,
    Error,
    Errors,
    ErrorSeverity,
    async_map,
    async_flat_map,
    collect_results,
    first_success,
)

__all__ = [
    "Result",
    "Error",
    "Errors",
    "ErrorSeverity",
    "async_map",
    "async_flat_map",
    "collect_results",
    "first_success",
]
