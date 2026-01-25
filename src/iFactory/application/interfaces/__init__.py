"""
Application Interfaces (Ports) Package.

Xuất các Interface để tầng Infrastructure và Presentation sử dụng.
"""

from .unit_of_work import IUnitOfWork
from .repository import IRepository
from .cache_provider import ICacheProvider
from .logger import ILogger

__all__ = ["IUnitOfWork", "IRepository", "ICacheProvider", "ILogger"]
