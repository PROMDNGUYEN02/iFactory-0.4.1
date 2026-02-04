# src/iFactory/infrastructure/observability/logging.py
"""Structured logging configuration."""

from __future__ import annotations

import logging
import sys
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


_log_context: ContextVar[dict[str, Any]] = ContextVar("log_context", default={})


@dataclass
class LogContext:
    """Context manager for contextual logging."""

    _data: dict[str, Any] = field(default_factory=dict)
    _token: Any = None

    def __enter__(self) -> "LogContext":
        current = _log_context.get().copy()
        current.update(self._data)
        self._token = _log_context.set(current)
        return self

    def __exit__(self, *args: Any) -> None:
        if self._token:
            _log_context.reset(self._token)

    @classmethod
    def set(cls, **kwargs: Any) -> "LogContext":
        ctx = cls()
        ctx._data = kwargs
        return ctx

    @classmethod
    def get(cls) -> dict[str, Any]:
        return _log_context.get().copy()


class StructuredLogger:
    """Logger with structured output."""

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)
        self._name = name

    def _format(self, message: str, **kwargs: Any) -> str:
        context = LogContext.get()
        all_fields = {**context, **kwargs}
        if all_fields:
            extras = " | ".join(f"{k}={v}" for k, v in all_fields.items())
            return f"{message} | {extras}"
        return message

    def debug(self, message: str, **kwargs: Any) -> None:
        self._logger.debug(self._format(message, **kwargs))

    def info(self, message: str, **kwargs: Any) -> None:
        self._logger.info(self._format(message, **kwargs))

    def warning(self, message: str, **kwargs: Any) -> None:
        self._logger.warning(self._format(message, **kwargs))

    def error(self, message: str, **kwargs: Any) -> None:
        self._logger.error(self._format(message, **kwargs))

    def exception(self, message: str, **kwargs: Any) -> None:
        self._logger.exception(self._format(message, **kwargs))

    def critical(self, message: str, **kwargs: Any) -> None:
        self._logger.critical(self._format(message, **kwargs))


class StructuredFormatter(logging.Formatter):
    """Custom formatter."""

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).isoformat()
        base = f"{timestamp} | {record.levelname:<8} | {record.name} | {record.getMessage()}"
        if record.exc_info:
            base += f"\n{self.formatException(record.exc_info)}"
        return base


def configure_logging(
    level: int | str = logging.INFO,
    json_format: bool = False,
    log_file: str | None = None,
) -> None:
    """Configure application logging."""
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    handlers: list[logging.Handler] = [logging.StreamHandler(sys.stdout)]

    if log_file:
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    for handler in handlers:
        handler.setFormatter(StructuredFormatter())

    logging.basicConfig(level=level, handlers=handlers, force=True)

    # Reduce noise
    for name in ["sqlalchemy", "asyncio", "PySide6"]:
        logging.getLogger(name).setLevel(logging.WARNING)


_loggers: dict[str, StructuredLogger] = {}


def get_logger(name: str) -> StructuredLogger:
    """Get or create a structured logger."""
    if name not in _loggers:
        _loggers[name] = StructuredLogger(name)
    return _loggers[name]


__all__ = [
    "configure_logging",
    "StructuredLogger",
    "get_logger",
    "LogContext",
]
