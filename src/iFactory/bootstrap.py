"""
Application Bootstrapper.
Entry point with optimized initialization.
"""

import asyncio
import logging
import sys
from typing import Optional

import iFactory.infrastructure.configuration  # noqa: F401

logger = logging.getLogger(__name__)


def configure_logging() -> None:
    """Configure application logging."""
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Silence noisy libraries
    for noisy in ("aiosqlite", "qasync", "sqlalchemy.engine", "faker"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def init_database() -> None:
    """Initialize storage database."""
    try:
        from iFactory.infrastructure.configuration.paths import PATHS

        PATHS.ensure_directories()

        from iFactory.infrastructure.persistence.sqlalchemy.database import (
            get_storage_engine,
        )

        storage_engine = get_storage_engine()

        from iFactory.infrastructure.persistence.sqlalchemy.models import StorageBase

        async with storage_engine.begin() as conn:
            await conn.run_sync(StorageBase.metadata.create_all)
        logger.debug("Storage tables initialized")

    except ImportError as e:
        logger.error(f"Configuration or Persistence module missing: {e}")
        raise
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


def create_qt_application():
    """Create and configure QApplication."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    if QApplication.instance():
        return QApplication.instance()

    app = QApplication(sys.argv)
    app.setApplicationName("iFactory")
    app.setQuitOnLastWindowClosed(True)

    try:
        from iFactory.presentation.constants.status import APP_ICON_PATH

        if APP_ICON_PATH:
            app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    except ImportError:
        pass

    return app


def run_application() -> int:
    """Run the application."""
    configure_logging()
    logger.info("=" * 60)
    logger.info("iFactory starting...")
    logger.info("=" * 60)

    try:
        # Initialize databases
        logger.info("Initializing database...")

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(init_database())
        logger.info("Database initialized successfully")

        # Create Qt Application
        qt_app = create_qt_application()

        # Run via ApplicationRunner
        from iFactory.shared.di.application_runner import ApplicationRunner

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

        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error", message)
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)


__all__ = ["run_application", "configure_logging", "init_database"]
