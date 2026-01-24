"""
Application Bootstrapper.

Single entry point that:
1. Configures logging
2. Creates QApplication
3. Initializes DI container
4. Runs the application

This is the ONLY file that knows about ALL layers.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure application logging."""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    for noisy in ("aiosqlite", "qasync", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def create_qt_application():
    """Create and configure QApplication."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("iFactory")
    app.setQuitOnLastWindowClosed(True)
    try:
        from iFactory.config import APP_ICON_PATH

        if APP_ICON_PATH:
            app.setWindowIcon(QIcon(APP_ICON_PATH))
    except ImportError:
        pass
    return app


def run_application() -> int:
    """
    Run the application.

    This is the main entry point that orchestrates everything.

    Returns:
        Exit code (0 for success)
    """
    configure_logging()
    logger.info("=" * 60)
    logger.info("iFactory starting...")
    logger.info("=" * 60)
    try:
        qt_app = create_qt_application()
        from iFactory.shared.di import ApplicationRunner

        runner = ApplicationRunner(qt_app)
        return runner.run()
    except Exception as e:
        logger.exception(f"Fatal error: {e}")
        _show_error(f"Application failed:\n\n{e}")
        return 1


def _show_error(message: str) -> None:
    """Show error dialog."""
    try:
        from PySide6.QtWidgets import QApplication, QMessageBox

        if QApplication.instance():
            QMessageBox.critical(None, "Fatal Error", message)
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)
