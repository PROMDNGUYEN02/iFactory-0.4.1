"""
Application Runner - Optimized with Deferred Data Loading.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING, Optional

from PySide6.QtWidgets import QApplication
import qasync

from .app_container import AppContainer

if TYPE_CHECKING:
    from iFactory.presentation.di.container import UIContainer

logger = logging.getLogger(__name__)

_CLEANUP_TIMEOUT = 2.0  # Reduced timeout


class ApplicationRunner:
    """
    Runs the Qt application with optimized startup.
    """

    __slots__ = ("qt_app", "container", "_ui_container", "main_window", "_loop")

    def __init__(self, qt_app: QApplication) -> None:
        """Initialize runner with Qt application."""
        self.qt_app = qt_app
        self.container: Optional[AppContainer] = None
        self._ui_container: Optional["UIContainer"] = None
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

                if self._ui_container:
                    self._ui_container.schedule_deferred_data_load()

                return self._loop.run_forever()

        except Exception as e:
            logger.exception(f"Application run failed: {e}")
            return 1
        finally:
            self._cleanup()

    async def _initialize(self) -> None:
        """Initialize application - fast path only."""
        try:
            self.container = AppContainer()
            await self.container.initialize()
            logger.info("AppContainer initialized")

            if hasattr(self.container, "get_ui_container"):
                self._ui_container = self.container.get_ui_container()

            if not self._ui_container:
                logger.info("[ApplicationRunner] Creating UIContainer manually")
                from iFactory.presentation.di.container import UIContainer

                self._ui_container = UIContainer(self.container)
                self._ui_container.initialize()

            self.main_window = self._ui_container.get_main_window()

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

    def _cleanup(self) -> None:
        """Cleanup resources."""
        logger.info("Cleaning up application...")

        # Shutdown UI first (this stops timers and async executors)
        if hasattr(self, "_ui_container") and self._ui_container:
            try:
                self._ui_container.shutdown()
            except Exception as e:
                logger.warning(f"UI shutdown error: {e}")

        # Brief pause to let pending operations complete
        if self._loop and not self._loop.is_closed():
            try:
                # Give a short time for cleanup
                self._loop.run_until_complete(asyncio.sleep(0.1))
            except Exception:
                pass

        # Cleanup container
        if self.container and self._loop and not self._loop.is_closed():
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
