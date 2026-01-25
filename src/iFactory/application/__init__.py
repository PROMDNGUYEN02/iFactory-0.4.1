"""
Application Layer Package.

Entry point for the application orchestration layer.
Exports Use Cases, DTOs, and Interfaces required by other layers.
NOTE: UI logic (View Models, Facades) has been moved to the Presentation layer.
"""

# 1. DTOs (Pure Data Transfer Objects)
from .dtos.order_dtos import OrderDTO, OrderItemDTO, CreateOrderRequestDTO, ApproveOrderRequestDTO
from .dtos.pagination import PaginatedResponseDTO

# 2. Interfaces (Ports)
from .interfaces.unit_of_work import IUnitOfWork
from .interfaces.repository import IRepository
from .interfaces.logger import ILogger
from .interfaces.security import ISecurityService

# 3. Use Cases (Interactors)
from .use_cases.order.create_order_use_case import CreateOrderUseCase
from .use_cases.order.approve_order_use_case import ApproveOrderUseCase
from .use_cases.order.get_order_use_case import GetOrderUseCase

# 4. Application Exceptions
from .exceptions import ApplicationException, ResourceNotFoundException, UnauthorizedActionException, DomainConstraintViolationException

__all__ = [
    # DTOs
    "OrderDTO",
    "OrderItemDTO",
    "CreateOrderRequestDTO",
    "ApproveOrderRequestDTO",
    "PaginatedResponseDTO",
    # Interfaces
    "IUnitOfWork",
    "IRepository",
    "ILogger",
    "ISecurityService",
    # Use Cases
    "CreateOrderUseCase",
    "ApproveOrderUseCase",
    "GetOrderUseCase",
    # Exceptions
    "ApplicationException",
    "ResourceNotFoundException",
    "UnauthorizedActionException",
    "DomainConstraintViolationException",
]
