from __future__ import annotations

from typing import Any, Dict, Optional


class DomainError(Exception):
    """
    Base class for all domain layer exceptions.
    Should include a message and optional context data for debugging.
    """

    def __init__(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.context = context or {}

    def __str__(self) -> str:
        return f"{self.message} | Context: {self.context}" if self.context else self.message
