from __future__ import annotations
from ..enums.machine_status import MachineStatus
from ..exceptions.device_exceptions import InvalidStatusTransitionError


class StatusTransitionPolicy:
    """
    Domain Policy enforcing rules about valid machine state transitions.
    Keeps business rule complexity out of the Entity, allowing for easy expansion.
    """

    @staticmethod
    def validate(current_status: MachineStatus, next_status: MachineStatus) -> None:
        """
        Validates if moving from current_status to next_status is legally allowed.
        Throws InvalidStatusTransitionError if the transition is prohibited by business rules.
        """
        if current_status == next_status:
            return

        # Business Rule: Machine in ALARM cannot directly go to RUNNING without passing through STOPPED/MAINTENANCE.
        if current_status == MachineStatus.ALARM and next_status == MachineStatus.RUNNING:
            raise InvalidStatusTransitionError.illegal_transition(current_status.value, next_status.value)

        # Business Rule: SHUTDOWN can only transition to STOPPED or UNKNOWN.
        if current_status == MachineStatus.SHUTDOWN and next_status == MachineStatus.RUNNING:
            raise InvalidStatusTransitionError.illegal_transition(current_status.value, next_status.value)
