# src/iFactory/domain/policies/transition_policy.py
"""
Status Transition Policy.

Domain policy enforcing rules about valid machine state transitions.
"""

from __future__ import annotations

from typing import Dict, FrozenSet, List, Set, Tuple

from ..enums.machine_status import MachineStatus
from ..exceptions.domain_exceptions import InvalidStatusTransitionError


class StatusTransitionPolicy:
    """
    Domain Policy enforcing rules about valid machine state transitions.

    This policy defines which status transitions are allowed and which
    are forbidden based on business rules.

    Business Rules:
    - Cannot go directly from ALARM to RUNNING (must clear alarm first)
    - Cannot go directly from SHUTDOWN to RUNNING (must restart)
    - Cannot go directly from MAINTENANCE to RUNNING (must complete maintenance)

    Usage:
        # Validate (raises exception if invalid)
        StatusTransitionPolicy.validate(
            current=MachineStatus.STOPPED,
            next=MachineStatus.RUNNING
        )

        # Check without exception
        if StatusTransitionPolicy.is_valid_transition(current, next):
            device.update_status(next)

        # Get allowed transitions
        allowed = StatusTransitionPolicy.get_allowed_transitions(current)
    """

    # Forbidden direct transitions
    _FORBIDDEN_TRANSITIONS: FrozenSet[Tuple[MachineStatus, MachineStatus]] = frozenset(
        {
            # Cannot start running directly from these states
            (MachineStatus.ALARM, MachineStatus.RUNNING),
            (MachineStatus.SHUTDOWN, MachineStatus.RUNNING),
            (MachineStatus.MAINTENANCE, MachineStatus.RUNNING),
        }
    )

    # Explicit allowed transitions (for documentation and UI)
    _ALLOWED_TRANSITIONS: Dict[MachineStatus, Set[MachineStatus]] = {
        MachineStatus.UNKNOWN: {
            MachineStatus.RUNNING,
            MachineStatus.STOPPED,
            MachineStatus.SHUTDOWN,
            MachineStatus.MAINTENANCE,
            MachineStatus.ALARM,
        },
        MachineStatus.RUNNING: {
            MachineStatus.STOPPED,
            MachineStatus.SHUTDOWN,
            MachineStatus.ALARM,
            MachineStatus.MAINTENANCE,
        },
        MachineStatus.STOPPED: {
            MachineStatus.RUNNING,
            MachineStatus.SHUTDOWN,
            MachineStatus.MAINTENANCE,
            MachineStatus.ALARM,
        },
        MachineStatus.SHUTDOWN: {
            MachineStatus.STOPPED,  # Must go through STOPPED to start
            MachineStatus.MAINTENANCE,
            MachineStatus.ALARM,
        },
        MachineStatus.MAINTENANCE: {
            MachineStatus.STOPPED,  # Must go through STOPPED to start
            MachineStatus.SHUTDOWN,
            MachineStatus.ALARM,
        },
        MachineStatus.ALARM: {
            MachineStatus.STOPPED,  # Clear alarm goes to STOPPED
            MachineStatus.SHUTDOWN,
            MachineStatus.MAINTENANCE,
        },
    }

    @classmethod
    def validate(
        cls,
        current_status: MachineStatus,
        next_status: MachineStatus,
    ) -> None:
        """
        Validate if a transition from current to next status is legal.

        Args:
            current_status: Current machine status
            next_status: Desired next status

        Raises:
            InvalidStatusTransitionError: If transition is not allowed
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
        """
        Check transition validity without raising exceptions.

        Args:
            current_status: Current machine status
            next_status: Desired next status

        Returns:
            True if transition is allowed
        """
        if current_status == next_status:
            return True
        return (current_status, next_status) not in cls._FORBIDDEN_TRANSITIONS

    @classmethod
    def get_allowed_transitions(
        cls,
        current_status: MachineStatus,
    ) -> List[MachineStatus]:
        """
        Get list of statuses that can be transitioned to from current status.

        Useful for UI to show available actions.

        Args:
            current_status: Current machine status

        Returns:
            List of allowed next statuses
        """
        return list(cls._ALLOWED_TRANSITIONS.get(current_status, set()))

    @classmethod
    def get_transition_path(
        cls,
        from_status: MachineStatus,
        to_status: MachineStatus,
    ) -> List[MachineStatus]:
        """
        Find shortest path of transitions from one status to another.

        Useful for automated state management.

        Args:
            from_status: Starting status
            to_status: Target status

        Returns:
            List of statuses to transition through (excluding start, including end)
            Empty list if already at target or no path exists
        """
        if from_status == to_status:
            return []

        # Direct transition possible?
        if cls.is_valid_transition(from_status, to_status):
            return [to_status]

        # BFS to find shortest path
        from collections import deque

        visited: Set[MachineStatus] = {from_status}
        queue: deque = deque([(from_status, [])])

        while queue:
            current, path = queue.popleft()

            for next_status in cls._ALLOWED_TRANSITIONS.get(current, set()):
                if next_status in visited:
                    continue

                new_path = path + [next_status]

                if next_status == to_status:
                    return new_path

                visited.add(next_status)
                queue.append((next_status, new_path))

        return []  # No path found

    @classmethod
    def can_reach(
        cls,
        from_status: MachineStatus,
        to_status: MachineStatus,
    ) -> bool:
        """Check if target status is reachable from current status."""
        return bool(cls.get_transition_path(from_status, to_status)) or from_status == to_status

    @classmethod
    def get_intermediate_status(
        cls,
        from_status: MachineStatus,
        to_status: MachineStatus,
    ) -> MachineStatus | None:
        """
        Get the intermediate status needed for an indirect transition.

        Returns None if direct transition is allowed.
        """
        if cls.is_valid_transition(from_status, to_status):
            return None

        path = cls.get_transition_path(from_status, to_status)
        return path[0] if path else None


__all__ = ["StatusTransitionPolicy"]
