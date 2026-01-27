"""Redux-like State Management for Presentation Layer."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


@dataclass
class Action:
    """Immutable action representing a state change intent."""

    type: str
    payload: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class Store(QObject):
    """Centralized state container following Redux pattern."""

    state_changed = Signal(dict)

    def __init__(
        self,
        initial_state: Dict[str, Any],
        reducers: Dict[str, Callable],
    ):
        super().__init__()
        self._state = initial_state.copy()
        self._reducers = reducers.copy()
        logger.debug("[Store] Initialized.")

    def dispatch(self, action: Action) -> None:
        """Process action through reducers and emit state change."""
        old_state = self._state.copy()

        for key, reducer in self._reducers.items():
            if key == "root":
                self._state = reducer(self._state, action)
            elif key in self._state:
                self._state[key] = reducer(self._state[key], action)

        if old_state != self._state:
            self.state_changed.emit(self.get_state())
            logger.debug(f"[Store] State changed: {action.type}")

    def get_state(self) -> Dict[str, Any]:
        """Return copy of current state."""
        return self._state.copy()

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        """Subscribe to state changes. Returns unsubscribe function."""
        self.state_changed.connect(callback)
        return lambda: self.state_changed.disconnect(callback)


__all__ = ["Action", "Store"]
