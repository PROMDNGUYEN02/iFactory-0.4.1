from __future__ import annotations
from .base import DomainError


class InvalidEquipmentCodeError(DomainError):
    @classmethod
    def empty(cls) -> InvalidEquipmentCodeError:
        return cls("Equipment code cannot be empty.")

    @classmethod
    def invalid_format(cls, code: str) -> InvalidEquipmentCodeError:
        return cls(f"Invalid equipment code format: '{code}'. Expected 2-4 uppercase letters followed by numbers.")


class InvalidStatusTransitionError(DomainError):
    @classmethod
    def illegal_transition(cls, from_status: str, to_status: str) -> InvalidStatusTransitionError:
        return cls(f"Illegal status transition from '{from_status}' to '{to_status}'.")
