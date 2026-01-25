from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from src.application.exceptions import ResourceNotFoundException, UnauthorizedActionException, DomainConstraintViolationException
from src.presentation.api.schemas.common import ErrorResponse


def register_exception_handlers(app: FastAPI):
    @app.exception_handler(ResourceNotFoundException)
    async def resource_not_found_handler(request: Request, exc: ResourceNotFoundException):
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=ErrorResponse(code="NOT_FOUND", message=str(exc)).dict())

    @app.exception_handler(UnauthorizedActionException)
    async def unauthorized_handler(request: Request, exc: UnauthorizedActionException):
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=ErrorResponse(code="FORBIDDEN", message=str(exc)).dict())

    @app.exception_handler(DomainConstraintViolationException)
    async def domain_constraint_handler(request: Request, exc: DomainConstraintViolationException):
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content=ErrorResponse(code="BAD_REQUEST", message=str(exc)).dict())
