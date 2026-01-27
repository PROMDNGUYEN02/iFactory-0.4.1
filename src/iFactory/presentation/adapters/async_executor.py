"""
Async Executor - Runs coroutines in background threads for Qt.
"""

from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Optional, TypeVar

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AsyncExecutor(QObject):
    """Executes async coroutines from Qt main thread."""

    task_completed = Signal(object)
    task_failed = Signal(str)

    def __init__(self, max_workers: int = 4, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._running = True

    def run(
        self,
        coro: Awaitable[T],
        callback: Optional[Callable[[T], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        if not self._running:
            return

        def _run_in_thread():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                result = loop.run_until_complete(coro)
                if callback:
                    QTimer.singleShot(0, lambda: callback(result))
                self.task_completed.emit(result)
            except Exception as e:
                logger.error(f"[AsyncExecutor] Task failed: {e}")
                if error_callback:
                    QTimer.singleShot(0, lambda: error_callback(e))
                self.task_failed.emit(str(e))
            finally:
                loop.close()

        self._executor.submit(_run_in_thread)

    def shutdown(self, wait: bool = True) -> None:
        self._running = False
        self._executor.shutdown(wait=wait)
