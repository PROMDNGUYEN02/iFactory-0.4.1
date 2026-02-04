# src/iFactory/domain/exceptions/base.py
"""
Base Domain Exception Classes.

Provides the foundation for domain-specific exceptions with
rich context and error handling capabilities.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class DomainError(Exception):
    """
    Base class for all domain exceptions.

    Features:
    - Error code for programmatic handling
    - Context dictionary for additional details
    - Structured error representation

    Usage:
        class InsufficientFundsError(DomainError):
            def __init__(self, account_id: str, required: Decimal, available: Decimal):
                super().__init__(
                    message=f"Insufficient funds in account {account_id}",
                    context={
                        "account_id": account_id,
                        "required": str(required),
                        "available": str(available),
                        "shortfall": str(required - available),
                    },
                    error_code="INSUFFICIENT_FUNDS"
                )
    """

    def __init__(
        self,
        message: str,
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
    ) -> None:
        super().__init__(message)
        self._message = message
        self._context = context or {}
        self._error_code = error_code or self._generate_error_code()

    @property
    def message(self) -> str:
        """Human-readable error message."""
        return self._message

    @property
    def context(self) -> Dict[str, Any]:
        """Additional context about the error."""
        return self._context.copy()

    @property
    def error_code(self) -> str:
        """Machine-readable error code."""
        return self._error_code

    def _generate_error_code(self) -> str:
        """Generate error code from class name."""
        name = self.__class__.__name__
        # Convert CamelCase to SCREAMING_SNAKE_CASE
        import re

        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).upper()

    def with_context(self, **kwargs: Any) -> "DomainError":
        """Return new error with additional context."""
        new_context = {**self._context, **kwargs}
        return self.__class__(
            message=self._message,
            context=new_context,
            error_code=self._error_code,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize error for API responses."""
        return {
            "error_code": self._error_code,
            "message": self._message,
            "context": self._context,
            "type": self.__class__.__name__,
        }

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self._message!r}, context={self._context})"


class DomainValidationError(DomainError):
    """
    Raised when domain validation fails.

    Used for aggregate/entity invariant violations.
    """

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        if field:
            ctx["field"] = field
        super().__init__(message, ctx, "VALIDATION_ERROR")

    @property
    def field(self) -> Optional[str]:
        """The field that failed validation."""
        return self._context.get("field")


class DomainInvariantError(DomainError):
    """
    Raised when an aggregate invariant is violated.

    Invariants are business rules that must always be true.
    """

    def __init__(
        self,
        invariant: str,
        aggregate_type: str,
        aggregate_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx.update(
            {
                "invariant": invariant,
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
            }
        )
        super().__init__(
            message=f"Invariant '{invariant}' violated for {aggregate_type}[{aggregate_id}]",
            context=ctx,
            error_code="INVARIANT_VIOLATED",
        )


class EntityNotFoundError(DomainError):
    """Raised when an entity cannot be found."""

    def __init__(
        self,
        entity_type: str,
        entity_id: Any,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx.update(
            {
                "entity_type": entity_type,
                "entity_id": str(entity_id),
            }
        )
        super().__init__(
            message=f"{entity_type} with ID '{entity_id}' not found",
            context=ctx,
            error_code="ENTITY_NOT_FOUND",
        )


class BusinessRuleViolationError(DomainError):
    """Raised when a business rule is violated."""

    def __init__(
        self,
        rule: str,
        message: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        ctx = context or {}
        ctx["rule"] = rule
        super().__init__(
            message=message,
            context=ctx,
            error_code="BUSINESS_RULE_VIOLATION",
        )


__all__ = [
    "DomainError",
    "DomainValidationError",
    "DomainInvariantError",
    "EntityNotFoundError",
    "BusinessRuleViolationError",
]
