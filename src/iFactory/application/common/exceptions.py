"""
Application Layer Exceptions.
"""


class ApplicationException(Exception):
    """Base exception for all application layer errors."""

    pass


class ResourceNotFoundException(ApplicationException):
    """Raised when a requested resource is not found."""

    def __init__(self, message: str):
        super().__init__(message)


class RemoteSourceException(ApplicationException):
    """Raised when the remote data source (PLC/Database) fails."""

    pass
