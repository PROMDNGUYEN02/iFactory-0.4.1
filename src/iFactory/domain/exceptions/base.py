from __future__ import annotations
from typing import Any, Optional


class DomainError(Exception):
    """Base exception for all domain-level business rule violations."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        self.message = message
        self.details = details or {}
        super().__init__(self.message)
