"""
Production-ready logging configuration.

Provides structured logging with rotation, filtering, and
multiple output handlers (Console & File).

Features:
    - Thread-safe configuration.
    - Automatic log file rotation (size & count limits).
    - Dynamic level switching (DEBUG, INFO, WARNING, ERROR).
    - Noise filtering for third-party libraries (e.g., Matplotlib, SQLAlchemy).

Example:
    >>> from iFactory.config import setup_logging, get_logger
    >>> setup_logging(level="DEBUG", log_file="app.log")
    >>> logger = get_logger(__name__)
    >>> logger.info("Application started")
"""
from __future__ import annotations
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final, Optional, Union
__all__ = ['setup_logging', 'get_logger']
DEFAULT_LEVEL: Final[int] = logging.INFO
STANDARD_FORMAT: Final[str] = '%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)-25s | %(message)s'
DETAILED_FORMAT: Final[str] = '%(asctime)s.%(msecs)03d [%(levelname)-8s] %(name)-25s [%(filename)s:%(lineno)d] | %(message)s'
DATE_FORMAT: Final[str] = '%Y-%m-%d %H:%M:%S'
MAX_LOG_SIZE_BYTES: Final[int] = 10 * 1024 * 1024
BACKUP_COUNT: Final[int] = 5
NOISY_LOGGERS: Final[tuple[str, ...]] = ('PIL', 'matplotlib', 'urllib3', 'asyncio', 'sqlalchemy.engine', 'httpx', 'httpcore')

def setup_logging(level: Union[int, str]=DEFAULT_LEVEL, log_file: Optional[Union[Path, str]]=None, console: bool=True, detailed: bool=False) -> logging.Logger:
    """
    Configure application-wide logging.

    Sets up the root logger with console and/or file handlers.
    File handler uses rotation to prevent unbounded log file growth.

    Args:
        level: Logging level (e.g., DEBUG, INFO).
                   Can be an integer constant or a string name.
        log_file: Optional path for log file.
                    Directory will be created automatically.
        console: Enable console (stdout) output.
        detailed: If True, includes file and line numbers in log format.

    Returns:
        Configured root logger.

    Example:
        >>> setup_logging(
        ...     level="DEBUG",
        ...     log_file=Path("logs/app.log"),
        ...     detailed=True
        ... )
    """
    numeric_level = _normalize_level(level)
    log_format = DETAILED_FORMAT if detailed else STANDARD_FORMAT
    formatter = logging.Formatter(log_format, datefmt=DATE_FORMAT)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)
    _clear_handlers(root_logger)
    if console:
        _add_console_handler(root_logger, numeric_level, formatter)
    if log_file:
        _add_file_handler(root_logger, log_file, numeric_level, formatter)
    app_logger = logging.getLogger('iFactory')
    app_logger.setLevel(numeric_level)
    _configure_noisy_loggers()
    root_logger.info(f"Logging initialized: level={logging.getLevelName(numeric_level)}, console={console}, file={log_file or 'None'}")
    return root_logger

def _normalize_level(level: Union[int, str]) -> int:
    """
    Convert level to integer.

    Args:
        level: Logging level as int (e.g., 10) or string name.

    Returns:
        Corresponding integer logging level.
    """
    if isinstance(level, int):
        return level
    level_map = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING, 'WARN': logging.WARNING, 'ERROR': logging.ERROR, 'CRITICAL': logging.CRITICAL}
    return level_map.get(level.upper(), DEFAULT_LEVEL)

def _clear_handlers(logger: logging.Logger) -> None:
    """
    Remove all existing handlers from logger.

    Args:
        logger: Logger instance to clean up.
    """
    for handler in logger.handlers[:]:
        handler.close()
        logger.removeHandler(handler)

def _add_console_handler(logger: logging.Logger, level: int, formatter: logging.Formatter) -> None:
    """
    Add console (stdout) handler to logger.

    Args:
        logger: Logger instance.
        level: Logging level.
        formatter: Log formatter.
    """
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.set_name('console')
    logger.addHandler(handler)

def _add_file_handler(logger: logging.Logger, log_file: Union[Path, str], level: int, formatter: logging.Formatter) -> None:
    """
    Add rotating file handler to logger.

    Args:
        logger: Logger instance.
        log_file: Path or string to log file.
        level: Logging level.
        formatter: Log formatter.

    Raises:
        OSError: If file cannot be created or written to.
    """
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(log_path, maxBytes=MAX_LOG_SIZE_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8')
    handler.setLevel(level)
    handler.setFormatter(formatter)
    handler.set_name('file')
    logger.addHandler(handler)

def _configure_noisy_loggers() -> None:
    """
    Reduce verbosity of third-party loggers.

    Forces specific noisy libraries to WARNING level
    to prevent cluttering the console with debug messages.

    Handled libraries:
        - PIL (Imaging)
        - Matplotlib (Plotting)
        - urllib3 (Networking)
        - asyncio (Async I/O)
        - sqlalchemy.engine (Database ORM)
    """
    for logger_name in NOISY_LOGGERS:
        try:
            third_party_logger = logging.getLogger(logger_name)
            third_party_logger.setLevel(logging.WARNING)
        except Exception:
            pass

def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module.

    Automatically prefixes the logger name with 'iFactory.'
    to maintain a consistent namespace in the logs.

    Args:
        name: Module name (typically __name__).

    Returns:
        A configured logger instance.

    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Processing started")
    """
    if not name:
        return logging.getLogger('iFactory')
    if name.startswith('iFactory'):
        full_name = name
    elif name.startswith('src.iFactory'):
        full_name = name.replace('src.', '')
    else:
        full_name = f'iFactory.{name}'
    return logging.getLogger(full_name)