class ApplicationException(Exception):
    pass


class ResourceNotFoundException(ApplicationException):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(f"{resource} with ID/Code '{resource_id}' not found.")


class UnauthorizedActionException(ApplicationException):
    pass


class DomainConstraintViolationException(ApplicationException):
    def __init__(self, message: str):
        super().__init__(f"Business rule violation: {message}")
