# File: presentation/state/store.py
from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List

from PySide6.QtCore import QObject, Signal

from .actions import Action
from .reducers import INITIAL_STATE, root_reducer

logger = logging.getLogger(__name__)


class Store(QObject):
    state_changed = Signal(dict)

    def __init__(self, initial_state: Dict[str, Any] = None):
        super().__init__()
        self._state: Dict[str, Any] = (initial_state or INITIAL_STATE).copy()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        logger.debug("Store initialized with state keys: %s", list(self._state.keys()))

    def get_state(self) -> Dict[str, Any]:
        return self._state.copy()

    def dispatch(self, action: Action) -> None:
        if not isinstance(action, Action):
            logger.warning("Invalid action dispatched: %s", type(action))
            return

        old_state = self._state
        self._state = root_reducer(old_state, action)

        if self._state is not old_state:
            logger.debug("State changed via action: %s", action.type.name)
            self.state_changed.emit(self.get_state())

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        self._subscribers.append(callback)
        self.state_changed.connect(callback)

        def unsubscribe():
            if callback in self._subscribers:
                self._subscribers.remove(callback)
                self.state_changed.disconnect(callback)

        return unsubscribe


__all__ = ["Store"]
