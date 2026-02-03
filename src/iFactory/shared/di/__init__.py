# src/iFactory/shared/di/__init__.py
"""Shared DI Module."""

from .app_container import AppContainer
from .application_runner import ApplicationRunner, run_application

__all__ = [
    "AppContainer",
    "ApplicationRunner",
    "run_application",
]
