from __future__ import annotations
from ..value_objects.status import Status
from ..exceptions import InvalidStatusTransitionError


class StatusTransitionPolicy:
    """
    Domain Policy enforcing rules about valid machine state transitions.
    Keeps business rule complexity out of the Entity.
    """

    @staticmethod
    def validate(current_status: Status, next_status: Status) -> None:
        """
        Validates if moving from current_status to next_status is legally allowed.
        Throws InvalidStatusTransitionError if the transition is prohibited by business rules.
        """
        # Example Business Rule: A machine in ALARM cannot directly go to RUNNING without going through STOPPED or MAINTENANCE first.
        if current_status.is_alarm and next_status.is_running:
            raise InvalidStatusTransitionError.illegal_transition(current_status.name, next_status.name)

        # Example Business Rule: SHUTDOWN can only transition to STOPPED or UNKNOWN.
        if current_status.is_shutdown and next_status.is_running:
            raise InvalidStatusTransitionError.illegal_transition(current_status.name, next_status.name)

        # Other transitions are considered valid.
        return
