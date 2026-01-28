"""
Application Bootstrapper.

Single entry point that:
1. Configures logging
2. Initializes Database (Creates folders & tables if not exist)
3. Creates QApplication
4. Initializes DI container
5. Runs the application
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

    # Basic configuration
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s - %(message)s", handlers=[logging.StreamHandler(sys.stdout)])

    # Silence noisy libraries
    for noisy in ("aiosqlite", "qasync", "sqlalchemy.engine", "faker"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


async def init_database() -> None:
    """
    Initialize both Hot and Cold Storage databases.
    Uses conn.run_sync() to create tables with AsyncEngine.
    """
    try:
        # 1. Ensure physical directories exist
        from iFactory.infrastructure.configuration.paths import PATHS

        PATHS.ensure_directories()

        # 2. Get Async Engines
        from iFactory.infrastructure.persistence.sqlalchemy.database import (
            get_hot_engine,
            get_cold_engine,
        )

        hot_engine = get_hot_engine()
        cold_engine = get_cold_engine()

        # 3. Import Base classes to register metadata
        from iFactory.infrastructure.persistence.sqlalchemy.models import (
            HotBase,
            ColdBase,
        )

        # 4. Initialize Hot Store (latest status, latest inputs)
        async with hot_engine.begin() as conn:
            await conn.run_sync(HotBase.metadata.create_all)
        logger.debug("Hot Storage tables initialized.")

        # 5. Initialize Cold Store (status history, material history)
        async with cold_engine.begin() as conn:
            await conn.run_sync(ColdBase.metadata.create_all)
        logger.debug("Cold Storage tables initialized.")

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

    # Check if instance already exists (e.g. testing)
    if QApplication.instance():
        return QApplication.instance()

    app = QApplication(sys.argv)
    app.setApplicationName("iFactory")
    app.setQuitOnLastWindowClosed(True)

    try:
        from iFactory.presentation.constants.ui_constants import APP_ICON_PATH

        if APP_ICON_PATH:
            app.setWindowIcon(QIcon(str(APP_ICON_PATH)))
    except ImportError:
        pass

    return app


def run_application() -> int:
    """
    Run the application.
    """
    configure_logging()
    logger.info("=" * 60)
    logger.info("iFactory starting...")
    logger.info("=" * 60)

    try:
        # Initialize databases (Hot + Cold) before Qt App starts
        logger.info("Initializing database...")
        # Windows ProactorEventLoop policy fix for Python 3.8+
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(init_database())
        logger.info("Database initialized and tables verified successfully.")

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

        # Ensure we have an app instance to show the alert
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Fatal Error", message)
    except Exception:
        print(f"ERROR: {message}", file=sys.stderr)
