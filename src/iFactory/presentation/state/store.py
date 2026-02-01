"""
Redux-like Store for state management.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Callable, Dict, List

from PySide6.QtCore import QObject, Signal

from .actions import Action, ActionType
from .reducers import INITIAL_STATE, root_reducer

logger = logging.getLogger(__name__)


class Store(QObject):
    """
    Central state store with Qt signal integration.
    """

    state_changed = Signal(dict)
    devices_updated = Signal(dict)
    sync_completed_signal = Signal(dict)
    page_changed = Signal(str)

    def __init__(self, initial_state: Dict[str, Any] = None):
        super().__init__()
        self._state: Dict[str, Any] = (initial_state or INITIAL_STATE).copy()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._dispatch_count = 0
        logger.debug("Store initialized with state keys: %s", list(self._state.keys()))

    def get_state(self) -> Dict[str, Any]:
        """Get a copy of current state."""
        return self._state.copy()

    def dispatch(self, action: Action) -> None:
        """Dispatch an action to update state."""
        if not isinstance(action, Action):
            logger.warning("Invalid action dispatched: %s", type(action))
            return

        old_state = self._state
        self._state = root_reducer(old_state, action)
        self._dispatch_count += 1

        # Always emit for device-related actions
        if action.type in (ActionType.LOAD_DEVICES, ActionType.UPDATE_DEVICES):
            devices = self._state.get("devices", {})
            logger.info(f"[Store] Emitting devices_updated with {len(devices)} devices")
            self.devices_updated.emit(devices)

        if self._state is not old_state:
            logger.debug(
                "State changed via action: %s (#%d)",
                action.type.name,
                self._dispatch_count,
            )
            self.state_changed.emit(self.get_state())
            self._emit_specific_signals(action, old_state)

    def _emit_specific_signals(self, action: Action, old_state: Dict[str, Any]) -> None:
        """Emit specific signals based on action type."""

        if action.type == ActionType.SYNC_COMPLETED:
            self.sync_completed_signal.emit(action.payload or {})

        elif action.type == ActionType.SET_PAGE:
            new_page = self._state.get("current_page")
            old_page = old_state.get("current_page")
            if new_page != old_page:
                self.page_changed.emit(new_page)

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        """Subscribe to state changes."""
        self._subscribers.append(callback)
        self.state_changed.connect(callback)

        def unsubscribe():
            if callback in self._subscribers:
                self._subscribers.remove(callback)
                try:
                    self.state_changed.disconnect(callback)
                except RuntimeError:
                    pass

        return unsubscribe

    def get_dispatch_count(self) -> int:
        """Get total number of dispatches."""
        return self._dispatch_count


__all__ = ["Store"]
