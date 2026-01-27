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


async def init_database() -> None:
    """
    [FIXED] Khởi tạo Database Bất đồng bộ (Async).
    Sử dụng conn.run_sync() để tạo bảng với AsyncEngine.
    """
    try:
        logger.info("Initializing database...")
        # 1. Đảm bảo thư mục vật lý tồn tại
        from iFactory.infrastructure.config.app_paths import PATHS

        PATHS.ensure_directories()

        # 2. Lấy Async Engine
        from iFactory.infrastructure.persistence.sqlalchemy.engine import get_hot_engine, get_cold_engine

        hot_engine = get_hot_engine()
        cold_engine = get_cold_engine()

        # 3. Tạo bảng thông qua run_sync()
        from iFactory.infrastructure.persistence.sqlalchemy.models import Base

        # Khởi tạo Hot Store
        async with hot_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        # Khởi tạo Cold Store
        async with cold_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logger.info("Database initialized and tables verified successfully.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


def create_qt_application():
    """Create and configure QApplication."""
    from PySide6.QtWidgets import QApplication
    from PySide6.QtGui import QIcon

    app = QApplication(sys.argv)
    app.setApplicationName("iFactory")
    app.setQuitOnLastWindowClosed(True)
    try:
        from iFactory.presentation.constants.icons import APP_ICON_PATH

        if APP_ICON_PATH:
            app.setWindowIcon(QIcon(APP_ICON_PATH))
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
        # [FIXED] Chạy hàm khởi tạo database async bằng asyncio.run()
        # Việc này đảm bảo DB được tạo xong hoàn toàn TRƯỚC khi Qt App khởi chạy.
        asyncio.run(init_database())

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
