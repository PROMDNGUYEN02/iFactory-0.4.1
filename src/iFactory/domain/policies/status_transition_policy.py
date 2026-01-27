from __future__ import annotations

from typing import FrozenSet, Tuple

from ..enums.machine_status import MachineStatus
from ..exceptions.device_exceptions import InvalidStatusTransitionError


class StatusTransitionPolicy:
    """
    Domain Policy enforcing rules about valid machine state transitions.

    Encapsulates the state machine logic for device lifecycle management.
    This keeps complexity out of the Entity while providing a single source
    of truth for transition rules.
    """

    _FORBIDDEN_TRANSITIONS: FrozenSet[Tuple[MachineStatus, MachineStatus]] = frozenset(
        {
            (MachineStatus.ALARM, MachineStatus.RUNNING),
            (MachineStatus.SHUTDOWN, MachineStatus.RUNNING),
            (MachineStatus.MAINTENANCE, MachineStatus.RUNNING),
        }
    )

    _REQUIRES_INTERMEDIATE: FrozenSet[Tuple[MachineStatus, MachineStatus]] = frozenset(
        {
            (MachineStatus.ALARM, MachineStatus.RUNNING),
        }
    )

    @classmethod
    def validate(
        cls,
        current_status: MachineStatus,
        next_status: MachineStatus,
    ) -> None:
        if current_status == next_status:
            return

        transition = (current_status, next_status)

        if transition in cls._FORBIDDEN_TRANSITIONS:
            raise InvalidStatusTransitionError.illegal_transition(
                current_status.display_name,
                next_status.display_name,
            )

    @classmethod
    def is_valid_transition(
        cls,
        current_status: MachineStatus,
        next_status: MachineStatus,
    ) -> bool:
        if current_status == next_status:
            return True
        return (current_status, next_status) not in cls._FORBIDDEN_TRANSITIONS

    @classmethod
    def get_allowed_transitions(
        cls,
        current_status: MachineStatus,
    ) -> Tuple[MachineStatus, ...]:
        allowed = []
        for status in MachineStatus:
            if status != current_status:
                if (current_status, status) not in cls._FORBIDDEN_TRANSITIONS:
                    allowed.append(status)
        return tuple(allowed)

    @classmethod
    def requires_acknowledgment(cls, status: MachineStatus) -> bool:
        return status == MachineStatus.ALARM
