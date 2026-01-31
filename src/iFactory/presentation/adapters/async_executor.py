# File: presentation/adapters/async_executor.py
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Awaitable, Callable, Optional, TypeVar

from PySide6.QtCore import QObject, QTimer, Signal

logger = logging.getLogger(__name__)

T = TypeVar("T")


class AsyncExecutor(QObject):
    task_completed = Signal(object)
    task_failed = Signal(str)

    def __init__(self, max_workers: int = 4, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="AsyncExecutor")
        self._is_running = True

    def execute(
        self,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        if not self._is_running:
            logger.warning("AsyncExecutor is shutting down, task rejected")
            return

        def worker():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(coro)
                if on_success:
                    QTimer.singleShot(0, lambda r=result: on_success(r))
                self.task_completed.emit(result)
            except Exception as e:
                logger.error(f"AsyncExecutor task failed: {e}")
                if on_error:
                    QTimer.singleShot(0, lambda err=e: on_error(err))
                self.task_failed.emit(str(e))
            finally:
                loop.close()

        self._executor.submit(worker)

    def run(
        self,
        coro: Awaitable[T],
        callback: Optional[Callable[[T], None]] = None,
        error_callback: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        self.execute(coro, callback, error_callback)

    def shutdown(self, wait: bool = True) -> None:
        self._is_running = False
        self._executor.shutdown(wait=wait)
        logger.debug("AsyncExecutor shutdown complete")


__all__ = ["AsyncExecutor"]
