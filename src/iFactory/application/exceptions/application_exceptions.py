class ApplicationError(Exception):
    """Base class for all application-layer exceptions."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class DataSourceError(ApplicationError):
    """Raised when an external data source (MSSQL, API) fails."""

    pass


class SyncError(ApplicationError):
    """Raised when the synchronization workflow fails."""

    pass
