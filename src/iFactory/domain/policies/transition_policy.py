from __future__ import annotations

from typing import FrozenSet, Tuple

from ..enums.machine_status import MachineStatus
from ..exceptions.domain_exceptions import InvalidStatusTransitionError


class StatusTransitionPolicy:
    """
    Domain Policy enforcing rules about valid machine state transitions.
    """

    _FORBIDDEN_TRANSITIONS: FrozenSet[Tuple[MachineStatus, MachineStatus]] = frozenset(
        {
            (MachineStatus.ALARM, MachineStatus.RUNNING),
            (MachineStatus.SHUTDOWN, MachineStatus.RUNNING),
            (MachineStatus.MAINTENANCE, MachineStatus.RUNNING),
        }
    )

    @classmethod
    def validate(
        cls,
        current_status: MachineStatus,
        next_status: MachineStatus,
    ) -> None:
        """
        Validates if a transition from current to next status is legal.
        Raises InvalidStatusTransitionError if illegal.
        """
        if current_status == next_status:
            return

        transition = (current_status, next_status)

        if transition in cls._FORBIDDEN_TRANSITIONS:
            raise InvalidStatusTransitionError.illegal_transition(
                current_status.name,
                next_status.name,
            )

    @classmethod
    def is_valid_transition(
        cls,
        current_status: MachineStatus,
        next_status: MachineStatus,
    ) -> bool:
        """Predicate to check transition validity without raising exceptions."""
        if current_status == next_status:
            return True
        return (current_status, next_status) not in cls._FORBIDDEN_TRANSITIONS
