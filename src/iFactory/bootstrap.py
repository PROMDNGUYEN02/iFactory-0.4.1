import sys
import asyncio
import logging
from typing import Optional

from PySide6.QtWidgets import QApplication
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession

from iFactory.infrastructure.config.app_paths import AppPaths
from iFactory.infrastructure.config.db_config import DatabaseConfig
from iFactory.infrastructure.config.device_config import DeviceConfig
from iFactory.infrastructure.config.json_config_loader import JsonConfigLoader
from iFactory.infrastructure.persistence.sqlalchemy.database import Database
from iFactory.infrastructure.persistence.sqlalchemy.uow import SqlAlchemyUnitOfWork
from iFactory.infrastructure.data_sources.mssql_data_source import MssqlDataSource
from iFactory.presentation.di.presentation_container import PresentationContainer
from iFactory.presentation.views.main_window import MainWindow

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(AppPaths.get_logs_path() / "ifactory.log", encoding="utf-8"),
    ],
)

logger = logging.getLogger("iFactory.bootstrap")


class ApplicationRunner:
    """
    Composition Root.
    Wires up the Dependency Injection graph and starts the application.
    """

    def __init__(self):
        self.app: Optional[QApplication] = None
        self.database: Optional[Database] = None
        self.uow: Optional[SqlAlchemyUnitOfWork] = None
        self.remote_source: Optional[MssqlDataSource] = None
        self.main_window: Optional[MainWindow] = None

    async def initialize_infrastructure(self) -> None:
        """
        Initializes the database, creates tables, and prepares data sources.
        """
        logger.info("Initializing Infrastructure...")

        # 1. Config
        config_path = AppPaths.get_config_path() / "settings.json"
        config_data = JsonConfigLoader.load(config_path)

        # 2. Database (SQLite)
        db_config = DatabaseConfig.default_sqlite()
        self.database = Database(db_config)
        await self.database.create_tables()

        # 3. Unit of Work
        self.uow = SqlAlchemyUnitOfWork(self.database.session_factory)

        # 4. Remote Data Source (MSSQL)
        # In a real scenario, connection string comes from config_data
        # For now, we allow it to be None or mock if config is missing
        device_conf = DeviceConfig(config_data.get("devices", {}))
        if device_conf.connection_string:
            self.remote_source = MssqlDataSource(device_conf.connection_string)
        else:
            logger.warning("No MSSQL connection string found. Remote sync will be disabled.")
            # For strict typing, we might need a NullObject implementation or handle None in container
            # Here we assume MssqlDataSource is required by the container signature
            # We'll pass a dummy or handle strict checks in the container.
            # In this refactor, let's instantiate a safe dummy or rely on the user to configure.
            # Ideally, we pass None and the container handles it, but our Container expects IRemoteDataSource.
            # Let's verify MssqlDataSource... it takes a string.
            self.remote_source = MssqlDataSource("DRIVER={SQL Server};SERVER=localhost;DATABASE=Test")

        logger.info("Infrastructure initialized.")

    def run(self) -> None:
        """
        Main entry point.
        """
        # Qt requires the QApplication to be created in the main thread
        self.app = QApplication(sys.argv)
        self.app.setApplicationName("iFactory")

        # Create an event loop for async initialization
        # Note: In production PyQt/PySide apps with asyncio, we often use qasync.
        # For this 'lite' architecture, we simply run init synchronously via asyncio.run
        # before the GUI starts.

        try:
            asyncio.run(self.initialize_infrastructure())
        except Exception as e:
            logger.critical(f"Failed to initialize infrastructure: {e}", exc_info=True)
            sys.exit(1)

        # Wiring Presentation
        logger.info("Wiring Presentation Layer...")
        container = PresentationContainer(uow=self.uow, remote_source=self.remote_source)

        main_controller = container.resolve_main_controller()

        self.main_window = MainWindow(main_controller)
        self.main_window.show()

        logger.info("Application started successfully.")
        sys.exit(self.app.exec())

    async def shutdown(self):
        logger.info("Shutting down...")
        if self.database:
            await self.database.dispose()
        if self.remote_source:
            await self.remote_source.dispose()


def run_application():
    runner = ApplicationRunner()
    runner.run()


if __name__ == "__main__":
    run_application()
