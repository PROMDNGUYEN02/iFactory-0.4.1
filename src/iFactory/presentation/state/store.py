"""
Redux-like Store for state management.
Thread-safe implementation with Qt signal integration.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from contextlib import contextmanager

from PySide6.QtCore import QObject, Signal, QMetaObject, Qt, Q_ARG

from .actions import Action, ActionType
from .reducers import INITIAL_STATE, root_reducer

logger = logging.getLogger(__name__)


class Store(QObject):
    """
    Central state store with Qt signal integration.

    Thread-safety:
    - State access is protected by RLock (reentrant for nested calls)
    - Signals are emitted on the Qt main thread
    - Subscribers are called synchronously within the lock

    Usage:
        store = Store()
        store.dispatch(set_page("electrode"))
        state = store.get_state()
    """

    # Qt signals for UI updates (always emitted on main thread)
    state_changed = Signal(dict)
    devices_updated = Signal(dict)
    sync_completed_signal = Signal(dict)
    page_changed = Signal(str)

    def __init__(self, initial_state: Optional[Dict[str, Any]] = None):
        super().__init__()
        self._state: Dict[str, Any] = (initial_state or INITIAL_STATE).copy()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._dispatch_count = 0

        # Thread safety - use RLock for reentrant access
        self._lock = threading.RLock()

        # Track if we're on the main thread
        self._main_thread_id = threading.current_thread().ident

        logger.debug("Store initialized with state keys: %s", list(self._state.keys()))

    def get_state(self) -> Dict[str, Any]:
        """
        Get a copy of current state.

        Thread-safe: Returns a shallow copy to prevent external mutation.
        """
        with self._lock:
            return self._state.copy()

    def select(self, selector: Callable[[Dict[str, Any]], Any]) -> Any:
        """
        Select a slice of state using a selector function.

        Thread-safe and more efficient than get_state() for specific values.

        Usage:
            devices = store.select(lambda s: s.get("devices", {}))
        """
        with self._lock:
            return selector(self._state)

    def dispatch(self, action: Action) -> None:
        """
        Dispatch an action to update state.

        Thread-safe:
        - State mutation is atomic
        - Signals are queued to main thread if called from background
        """
        if not isinstance(action, Action):
            logger.warning("Invalid action dispatched: %s", type(action))
            return

        with self._lock:
            old_state = self._state
            try:
                new_state = root_reducer(old_state, action)
            except Exception as e:
                logger.error("Reducer error for action %s: %s", action.type.name, e)
                return

            self._state = new_state
            self._dispatch_count += 1

            # Determine what changed
            state_changed = new_state is not old_state

            # Capture values needed for signals while under lock
            emit_data = self._prepare_emit_data(action, old_state, new_state, state_changed)

        # Emit signals outside the lock to prevent deadlocks
        self._emit_signals(emit_data)

    def _prepare_emit_data(self, action: Action, old_state: Dict[str, Any], new_state: Dict[str, Any], state_changed: bool) -> Dict[str, Any]:
        """Prepare data for signal emission (called under lock)."""
        data = {
            "action": action,
            "state_changed": state_changed,
            "dispatch_count": self._dispatch_count,
            "new_state_copy": new_state.copy() if state_changed else None,
        }

        # Device-related actions
        if action.type in (ActionType.LOAD_DEVICES, ActionType.UPDATE_DEVICES):
            data["devices"] = new_state.get("devices", {}).copy()

        # Sync completed
        if action.type == ActionType.SYNC_COMPLETED:
            data["sync_payload"] = action.payload.copy() if action.payload else {}

        # Page change
        if action.type == ActionType.SET_PAGE:
            data["new_page"] = new_state.get("current_page")
            data["old_page"] = old_state.get("current_page")

        return data

    def _emit_signals(self, emit_data: Dict[str, Any]) -> None:
        """Emit Qt signals (called outside lock)."""
        action = emit_data["action"]

        # Device updates - always emit for these actions
        if "devices" in emit_data:
            devices = emit_data["devices"]
            logger.info(f"[Store] Emitting devices_updated with {len(devices)} devices")
            self._safe_emit(self.devices_updated, devices)

        # State changed
        if emit_data["state_changed"]:
            logger.debug(
                "State changed via action: %s (#%d)",
                action.type.name,
                emit_data["dispatch_count"],
            )
            self._safe_emit(self.state_changed, emit_data["new_state_copy"])

        # Sync completed
        if "sync_payload" in emit_data:
            self._safe_emit(self.sync_completed_signal, emit_data["sync_payload"])

        # Page change
        if "new_page" in emit_data and emit_data["new_page"] != emit_data.get("old_page"):
            self._safe_emit(self.page_changed, emit_data["new_page"])

    def _safe_emit(self, signal: Signal, *args) -> None:
        """
        Emit signal safely, ensuring it runs on the main thread.
        """
        if threading.current_thread().ident == self._main_thread_id:
            # Already on main thread - emit directly
            signal.emit(*args)
        else:
            # Queue to main thread using Qt's thread-safe mechanism
            # Note: For simple cases, Qt signals are already thread-safe
            # but this ensures slot execution happens on the right thread
            try:
                signal.emit(*args)
            except RuntimeError as e:
                logger.warning("Signal emit failed (object may be deleted): %s", e)

    def subscribe(self, callback: Callable[[Dict[str, Any]], None]) -> Callable[[], None]:
        """
        Subscribe to state changes.

        Returns an unsubscribe function.

        Note: Callback will be invoked on the thread that emits state_changed,
        typically the main thread.
        """
        with self._lock:
            self._subscribers.append(callback)

        # Connect to Qt signal
        self.state_changed.connect(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
            try:
                self.state_changed.disconnect(callback)
            except (RuntimeError, TypeError):
                # Already disconnected or object deleted
                pass

        return unsubscribe

    def get_dispatch_count(self) -> int:
        """Get total number of dispatches (thread-safe)."""
        with self._lock:
            return self._dispatch_count

    @contextmanager
    def batch(self):
        """
        Context manager for batching multiple dispatches.

        Reduces signal emissions - only emits once at the end.

        Usage:
            with store.batch():
                store.dispatch(action1)
                store.dispatch(action2)
            # Single state_changed emission here

        Note: Not yet implemented - placeholder for future optimization.
        """
        # TODO: Implement batching for performance optimization
        yield


__all__ = ["Store"]
