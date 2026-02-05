# src/iFactory/shared/di/application_runner.py
"""
Application Runner - Compatible with dependency-injector based AppContainer.

Handles Qt event loop integration with async initialization and cleanup.
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

_CLEANUP_TIMEOUT = 5.0


class ApplicationRunner:
    """
    Runs the Qt application with MVVM architecture.

    Compatible with both old-style AppContainer and new dependency-injector based container.
    """

    __slots__ = (
        "qt_app",
        "container",
        "_ui_container",
        "main_window",
        "_loop",
        "_cleanup_done",
    )

    def __init__(self, qt_app: QApplication) -> None:
        self.qt_app = qt_app
        self.container: Optional[AppContainer] = None
        self._ui_container: Optional["UIContainer"] = None
        self.main_window = None
        self._loop: Optional[qasync.QEventLoop] = None
        self._cleanup_done = False

    def run(self) -> int:
        """Main entry point - runs the application."""
        try:
            self._loop = qasync.QEventLoop(self.qt_app)
            asyncio.set_event_loop(self._loop)

            with self._loop:
                # Initialize
                self._loop.run_until_complete(self._initialize())

                if not self.main_window:
                    logger.error("No main window created!")
                    return 1

                # Show window
                self._show_window()

                # Start deferred data loading
                if self._ui_container:
                    self._ui_container.schedule_deferred_data_load()

                # Run until quit
                exit_code = self._loop.run_forever()

                # Cleanup while loop is still valid
                self._do_cleanup()

                return exit_code if isinstance(exit_code, int) else 0

        except Exception as e:
            logger.exception(f"Application run failed: {e}")
            return 1
        finally:
            # Final cleanup if not done
            if not self._cleanup_done:
                self._sync_cleanup()

    async def _initialize(self) -> None:
        """Async initialization of all components."""
        try:
            # Create and initialize container
            self.container = AppContainer()
            await self.container.initialize()
            logger.info("AppContainer initialized")

            # Get UI container
            self._ui_container = self.container.get_ui_container()

            if not self._ui_container:
                # Fallback: create UI container manually
                logger.info("[ApplicationRunner] Creating UIContainer manually")
                from iFactory.presentation.di.container import UIContainer

                self._ui_container = UIContainer(self.container)
                self._ui_container.initialize()

            # Get main window
            self.main_window = self._ui_container.get_main_window()

            # Run async initialization if available
            if hasattr(self._ui_container, "initialize_async"):
                await self._ui_container.initialize_async()

            logger.info("Application initialized with MVVM architecture")

        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    def _show_window(self) -> None:
        """Show the main window."""
        if self.main_window:
            self.main_window.show()
            self.qt_app.processEvents()
            self.main_window.repaint()
            self.qt_app.processEvents()
            logger.info("Main window shown")

    def _do_cleanup(self) -> None:
        """Cleanup while event loop is still available."""
        if self._cleanup_done:
            return

        logger.info("Cleaning up application...")

        # Step 1: Shutdown UI (stops timers, executors)
        if self._ui_container:
            try:
                self._ui_container.shutdown()
            except Exception as e:
                logger.warning(f"UI shutdown error: {e}")

        # Step 2: Process remaining Qt events
        try:
            self.qt_app.processEvents()
        except Exception:
            pass

        # Step 3: Run async cleanup if loop is available
        if self._loop and not self._loop.is_closed():
            try:
                self._loop.run_until_complete(asyncio.wait_for(self._async_cleanup(), timeout=_CLEANUP_TIMEOUT))
            except asyncio.TimeoutError:
                logger.warning("Async cleanup timed out")
            except RuntimeError as e:
                logger.debug(f"Async cleanup runtime: {e}")
            except Exception as e:
                logger.warning(f"Async cleanup error: {e}")

        self._cleanup_done = True
        logger.info("Application cleanup complete")

    def _sync_cleanup(self) -> None:
        """Synchronous fallback cleanup."""
        if self._cleanup_done:
            return

        logger.info("Cleaning up application (sync fallback)...")

        if self._ui_container:
            try:
                self._ui_container.shutdown()
            except Exception as e:
                logger.warning(f"UI shutdown error: {e}")

        self._cleanup_done = True
        logger.info("Application cleanup complete")

    async def _async_cleanup(self) -> None:
        """Async cleanup for database connections - IMPROVED."""

        # This avoids "Event loop is closed" errors
        cleanup_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(cleanup_loop)

        try:
            # Dispose container with new loop
            if self.container:
                try:
                    await self.container.dispose()
                    logger.info("Container disposed")
                except Exception as e:
                    logger.debug(f"Container dispose error: {e}")

            # Cancel any remaining tasks
            pending = asyncio.all_tasks(cleanup_loop)
            if pending:
                for task in pending:
                    task.cancel()

                # Wait for cancellations
                await asyncio.gather(*pending, return_exceptions=True)

        finally:
            # Close cleanup loop
            cleanup_loop.close()


def run_application() -> int:
    """Entry point for running the application."""
    app = QApplication(sys.argv)
    return ApplicationRunner(app).run()


__all__ = ["ApplicationRunner", "run_application"]
