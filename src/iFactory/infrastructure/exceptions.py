from typing import Optional


class InfrastructureError(Exception):
    def __init__(self, message: str, original_error: Optional[Exception] = None):
        self.message = message
        self.original_error = original_error
        super().__init__(self.message)


class PersistenceError(InfrastructureError):
    pass


class ExternalServiceError(InfrastructureError):
    pass


class ConnectionError(InfrastructureError):
    pass


class MappingError(InfrastructureError):
    pass
