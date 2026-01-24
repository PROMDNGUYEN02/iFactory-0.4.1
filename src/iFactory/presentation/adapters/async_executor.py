from __future__ import annotations
import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Awaitable, Callable, Optional, TypeVar
from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)
T = TypeVar("T")


class AsyncExecutor(QObject):
    task_completed = Signal(object)
    task_failed = Signal(str)

    def __init__(self, max_workers: int = 4, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._periodic_timers: dict[str, QTimer] = {}
        self._running = True

    def run(self, coro: Awaitable[T], callback=None, error_callback=None) -> None:
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
                logger.error(f"Async task failed: {e}")
                if error_callback:
                    QTimer.singleShot(0, lambda: error_callback(e))
                self.task_failed.emit(str(e))
            finally:
                loop.close()

        self._executor.submit(_run_in_thread)

    def run_in_background(self, coro, callback=None, error_callback=None):
        self.run(coro, callback, error_callback)

    def cancel_all_periodic(self) -> None:
        for task_id in list(self._periodic_timers.keys()):
            timer = self._periodic_timers.pop(task_id)
            timer.stop()
            timer.deleteLater()

    def shutdown(self, wait: bool = True) -> None:
        self._running = False
        self.cancel_all_periodic()
        self._executor.shutdown(wait=wait)
