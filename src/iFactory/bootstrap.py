# src/iFactory/bootstrap.py
"""
Application Bootstrapper.
Entry point with optimized initialization.
"""

import asyncio
import logging
import warnings
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

    # ✅ ADD: Suppress specific SQLAlchemy pool warnings
    logging.getLogger("sqlalchemy.pool.impl").setLevel(logging.CRITICAL)

    # ✅ ADD: Custom filter for asyncio to only suppress "Event loop is closed"
    class EventLoopFilter(logging.Filter):
        def filter(self, record):
            # Hide "Event loop is closed" and "Unclosed connection"
            if "Event loop is closed" in record.getMessage():
                return False
            if "Unclosed connection" in record.getMessage():
                return False
            return True

    asyncio_logger = logging.getLogger("asyncio")
    asyncio_logger.addFilter(EventLoopFilter())

    # ✅ ADD: Suppress ResourceWarnings about unclosed connections
    warnings.filterwarnings("ignore", message="unclosed", category=ResourceWarning)


async def init_database() -> None:
    """
    Initialize storage database directories.
    """
    try:
        from iFactory.infrastructure.configuration.paths import PATHS

        # Only ensure directories exist - don't create engine here!
        PATHS.ensure_directories()
        PATHS.initialize_config_files()

        logger.debug("[Bootstrap] Directories initialized")

    except ImportError as e:
        logger.error(f"Configuration module missing: {e}")
        raise
    except Exception as e:
        logger.error(f"Directory initialization failed: {e}")
        raise


def init_event_system() -> None:
    """Initialize domain event system."""
    try:
        from iFactory.application.event_handlers import register_event_handlers

        register_event_handlers()
        logger.info("Event system initialized")
    except ImportError as e:
        logger.warning(f"Event handlers not available: {e}")


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
        # Initialize directories (not database engine!)
        logger.info("Initializing directories...")

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

        asyncio.run(init_database())
        logger.info("Directories initialized successfully")

        # Initialize event system
        init_event_system()

        # Create Qt Application
        qt_app = create_qt_application()

        # Run via ApplicationRunner
        # AppContainer will handle database initialization
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
