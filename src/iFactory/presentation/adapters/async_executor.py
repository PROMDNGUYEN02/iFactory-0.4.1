import asyncio
import logging
from typing import Awaitable, Callable, Optional, TypeVar

from PySide6.QtCore import QObject, QThread, Signal, Slot

T = TypeVar("T")
logger = logging.getLogger(__name__)


class WorkerSignals(QObject):
    """Signals for the background worker."""

    finished = Signal()
    error = Signal(str)
    result = Signal(object)


class AsyncWorker(QObject):
    """
    Runs an asyncio coroutine in a separate thread managing its own event loop.
    """

    def __init__(self, coro: Awaitable[T]):
        super().__init__()
        self._coro = coro
        self.signals = WorkerSignals()

    @Slot()
    def run(self):
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._coro)
            self.signals.result.emit(result)
            loop.close()
        except Exception as e:
            logger.error(f"Async worker failed: {e}", exc_info=True)
            self.signals.error.emit(str(e))
        finally:
            self.signals.finished.emit()


class AsyncExecutor(QObject):
    """
    Adapter to bridge Qt (Sync) and Application Layer (Async).
    Executes use cases in background threads to keep UI responsive.
    """

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._active_threads = []

    def run(
        self,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Fire-and-forget execution of a coroutine with callback hooks.
        """
        thread = QThread()
        worker = AsyncWorker(coro)
        worker.moveToThread(thread)

        # Connect signals
        thread.started.connect(worker.run)

        if on_success:
            worker.signals.result.connect(on_success)

        if on_error:
            worker.signals.error.connect(on_error)

        # Cleanup
        worker.signals.finished.connect(thread.quit)
        worker.signals.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)

        # Keep reference to prevent GC
        self._active_threads.append(thread)
        thread.finished.connect(lambda: self._cleanup_thread(thread))

        thread.start()

    def _cleanup_thread(self, thread):
        if thread in self._active_threads:
            self._active_threads.remove(thread)
