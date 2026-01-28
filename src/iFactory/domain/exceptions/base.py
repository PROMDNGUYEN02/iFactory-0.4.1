from __future__ import annotations

from typing import Any, Dict, Optional


class DomainError(Exception):
    """
    Root exception for all Domain Layer violations.
    Infrastructure and UI should catch this to handle business failures.
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
