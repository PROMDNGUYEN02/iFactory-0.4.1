"""
Presentation Adapters.
Bridges infrastructure/application events (like async tasks) to UI-safe mechanisms (Qt Signals).
"""

from .qt_signal_adapter import QtSignalAdapter
from .async_executor import AsyncExecutor

__all__ = ["QtSignalAdapter", "AsyncExecutor"]
