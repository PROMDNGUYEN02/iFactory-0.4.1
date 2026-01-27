from __future__ import annotations

from typing import Any, Dict, Optional


class DomainError(Exception):
    """
    Base exception for all domain-level business rule violations.

    Domain errors represent invariant violations or illegal operations
    within the business logic layer.
    """

    __slots__ = ("_message", "_details")

    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._message = message
        self._details = details or {}
        super().__init__(self._message)

    @property
    def message(self) -> str:
        return self._message

    @property
    def details(self) -> Dict[str, Any]:
        return self._details.copy()

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._message!r})"
