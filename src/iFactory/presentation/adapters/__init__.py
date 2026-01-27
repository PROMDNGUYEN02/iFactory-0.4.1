"""
Presentation Adapters.
Bridges async/background events to UI-safe mechanisms.
"""

from .qt_signal_adapter import QtSignalAdapter
from .async_executor import AsyncExecutor

__all__ = ["QtSignalAdapter", "AsyncExecutor"]
