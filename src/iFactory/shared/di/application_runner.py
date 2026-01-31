"""
Application Runner - Optimized with Deferred Data Loading.
Clean Architecture Compliant.
"""

from __future__ import annotations
import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Optional
from PySide6.QtWidgets import QApplication
import qasync
from .app_container import AppContainer

# Deferred import to avoid circular dependencies at module level
if TYPE_CHECKING:
    from iFactory.presentation.di.ui_container import UIContainer

logger = logging.getLogger(__name__)

try:
    from iFactory.shared.utils.profiler import profile_block, startup_profiler

    _PROFILER_AVAILABLE = True
except ImportError:
    from contextlib import nullcontext

    def profile_block(_: str):
        return nullcontext()

    class _DummyProfiler:

        def reset(self) -> None:
            pass

        def checkpoint(self, _: str) -> None:
            pass

        def report(self) -> None:
            pass

        def get_slow_phases(self, _: int) -> list:
            return []

    startup_profiler = _DummyProfiler()
    _PROFILER_AVAILABLE = False

_CLEANUP_TIMEOUT = 5.0


class ApplicationRunner:
    """
    Runs the Qt application with optimized startup.

    Strategy:
    1. Initialize containers and create UI (fast)
    2. Show window immediately (skeleton/cached state)
    3. Load data in background (non-blocking)
    """

    __slots__ = ("qt_app", "container", "_ui_container", "main_window", "_loop")

    def __init__(self, qt_app: QApplication) -> None:
        """Initialize runner with Qt application."""
        startup_profiler.reset()
        self.qt_app = qt_app
        self.container: Optional[AppContainer] = None
        self._ui_container: Optional[UIContainer] = None
        self.main_window = None
        self._loop: Optional[qasync.QEventLoop] = None

    def run(self) -> int:
        """Run the application and return exit code."""
        try:
            self._loop = qasync.QEventLoop(self.qt_app)
            asyncio.set_event_loop(self._loop)
            with self._loop:
                self._loop.run_until_complete(self._initialize())
                if not self.main_window:
                    logger.error("No main window created!")
                    return 1
                self._show_window()

                # Deferred load handled by Redux Controller triggers
                # We trigger it explicitly to ensure data flow starts after render
                if self._ui_container:
                    self._ui_container.schedule_deferred_data_load()

                self._log_startup_performance()
                return self._loop.run_forever()
        except Exception as e:
            logger.exception(f"Application run failed: {e}")
            return 1
        finally:
            self._cleanup()

    async def _initialize(self) -> None:
        """Initialize application - fast path only."""
        try:
            # 1. Init App Container (Infra + App + Presentation DI)
            self.container = AppContainer()
            await self.container.initialize()
            logger.info("AppContainer initialized")

            # 2. Retrieve UI Container
            # Logic: AppContainer might have already initialized UI.
            # We try to get it first to avoid Double Initialization.
            if hasattr(self.container, "get_ui_container"):
                self._ui_container = self.container.get_ui_container()

            # Fallback: If AppContainer didn't create it, we do.
            if not self._ui_container:
                logger.info("[ApplicationRunner] UIContainer not found in AppContainer. Creating manual instance.")
                from iFactory.presentation.di.ui_container import UIContainer

                self._ui_container = UIContainer(self.container)
                self._ui_container.initialize()

            # 3. Retrieve the already-created main window
            self.main_window = self._ui_container.get_main_window()

            # 4. Final Async Hooks (if any)
            if hasattr(self._ui_container, "initialize_async"):
                await self._ui_container.initialize_async()

            logger.info("Application initialized successfully")
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def _show_window(self) -> None:
        """Show main window and process events."""
        if self.main_window:
            self.main_window.show()
            self.qt_app.processEvents()
            self.main_window.repaint()
            self.qt_app.processEvents()
            logger.info("Main window shown")

    def _log_startup_performance(self) -> None:
        """Log startup performance metrics."""
        if not _PROFILER_AVAILABLE:
            return
        startup_profiler.report()
        if slow := startup_profiler.get_slow_phases(2000):
            logger.warning(f"[PERF] Slow phases: {slow}")

    def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up application...")
        if hasattr(self, "_ui_container") and self._ui_container:
            self._ui_container.shutdown()

        if not self.container or not self._loop or self._loop.is_closed():
            return
        try:
            self._loop.run_until_complete(asyncio.wait_for(self._async_cleanup(), timeout=_CLEANUP_TIMEOUT))
        except asyncio.TimeoutError:
            logger.warning("Cleanup timed out")
        except Exception as e:
            logger.warning(f"Cleanup error: {e}")
        logger.info("Application cleanup complete")

    async def _async_cleanup(self) -> None:
        """Async cleanup operations."""
        if hasattr(self.container, "dispose"):
            await self.container.dispose()


def run_application() -> int:
    """Entry point for application."""
    app = QApplication(sys.argv)
    return ApplicationRunner(app).run()


__all__ = ["ApplicationRunner", "run_application"]
