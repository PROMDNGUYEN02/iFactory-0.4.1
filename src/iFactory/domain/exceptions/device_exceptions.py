from __future__ import annotations

from .base import DomainError


class InvalidEquipmentCodeError(DomainError):
    """Raised when an equipment code fails validation."""

    @classmethod
    def empty(cls) -> InvalidEquipmentCodeError:
        return cls("Equipment code cannot be empty.")

    @classmethod
    def too_long(cls, code: str, max_length: int) -> InvalidEquipmentCodeError:
        return cls(
            f"Equipment code '{code}' exceeds maximum length of {max_length}.",
            {"code": code, "max_length": max_length},
        )

    @classmethod
    def invalid_format(cls, code: str) -> InvalidEquipmentCodeError:
        return cls(
            f"Invalid equipment code format: '{code}'. " "Expected alphanumeric characters, hyphens, or underscores.",
            {"code": code},
        )


class InvalidStatusTransitionError(DomainError):
    """Raised when an illegal state transition is attempted."""

    @classmethod
    def illegal_transition(
        cls,
        from_status: str,
        to_status: str,
    ) -> InvalidStatusTransitionError:
        return cls(
            f"Illegal status transition from '{from_status}' to '{to_status}'.",
            {"from_status": from_status, "to_status": to_status},
        )


class DeviceNotFoundError(DomainError):
    """Raised when a device cannot be found via the repository."""

    @classmethod
    def by_code(cls, code: str) -> DeviceNotFoundError:
        return cls(
            f"Device with code '{code}' not found.",
            {"equipment_code": code},
        )
