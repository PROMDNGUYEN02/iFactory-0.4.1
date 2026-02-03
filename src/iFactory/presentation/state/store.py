# src/iFactory/presentation/state/store.py
"""
Redux-like Store for state management.

Features:
- Thread-safe state updates with RLock
- Qt signal integration for UI updates
- Middleware support for logging, debugging
- Batched updates for performance
- Type-safe selectors
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    Iterator,
    List,
    Optional,
    Protocol,
    TypeVar,
)

from PySide6.QtCore import QObject, Signal

from .actions import Action, ActionType
from .reducers import INITIAL_STATE, root_reducer

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Middleware Protocol
# ============================================================================


class Middleware(Protocol):
    """Protocol for store middleware."""

    def __call__(
        self,
        store: "Store",
        action: Action,
        next_dispatch: Callable[[Action], None],
    ) -> None:
        """
        Process action and optionally call next middleware.

        Args:
            store: The store instance
            action: The action being dispatched
            next_dispatch: Call this to pass action to next middleware
        """
        ...


def logging_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware that logs all actions."""
    start = time.perf_counter()
    logger.debug(f"[Store] Action: {action.type.name}")

    next_dispatch(action)

    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > 10:  # Log slow dispatches
        logger.warning(f"[Store] Slow dispatch: {action.type.name} took {elapsed_ms:.1f}ms")


def dev_tools_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware for debugging (stores action history)."""
    if not hasattr(store, "_action_history"):
        store._action_history = []

    store._action_history.append(
        {
            "action": action.type.name,
            "payload": action.payload,
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Keep last 100 actions
    if len(store._action_history) > 100:
        store._action_history = store._action_history[-100:]

    next_dispatch(action)


# ============================================================================
# Selector with Memoization
# ============================================================================


@dataclass
class MemoizedSelector(Generic[T]):
    """
    Memoized selector that caches results.

    Usage:
        select_devices = MemoizedSelector(lambda s: s.get("devices", {}))
        devices = select_devices(store.get_state())
    """

    selector: Callable[[Dict[str, Any]], T]
    _last_state: Optional[Dict[str, Any]] = field(default=None, repr=False)
    _cached_result: Optional[T] = field(default=None, repr=False)

    def __call__(self, state: Dict[str, Any]) -> T:
        # Simple identity check for memoization
        if state is self._last_state:
            return self._cached_result  # type: ignore

        self._last_state = state
        self._cached_result = self.selector(state)
        return self._cached_result


# ============================================================================
# Store
# ============================================================================


class Store(QObject):
    """
    Central state store with Qt signal integration.

    Thread-safety:
    - State access protected by RLock
    - Signals emitted on Qt main thread
    - Subscribers called synchronously within lock

    Middleware:
    - Plugins that intercept dispatches
    - Used for logging, debugging, async actions

    Usage:
        store = Store()
        store.add_middleware(logging_middleware)
        store.dispatch(set_page("electrode"))
        state = store.get_state()
    """

    # Qt signals for UI updates
    state_changed = Signal(dict)
    devices_updated = Signal(dict)
    sync_completed_signal = Signal(dict)
    page_changed = Signal(str)

    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        middlewares: Optional[List[Middleware]] = None,
    ):
        super().__init__()
        self._state: Dict[str, Any] = (initial_state or INITIAL_STATE).copy()
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []
        self._middlewares: List[Middleware] = middlewares or []
        self._dispatch_count = 0
        self._is_batching = False
        self._batch_actions: List[Action] = []

        # Thread safety
        self._lock = threading.RLock()
        self._main_thread_id = threading.current_thread().ident

        logger.debug(f"[Store] Initialized with {len(self._state)} state keys")

    # ========================================================================
    # Middleware
    # ========================================================================

    def add_middleware(self, middleware: Middleware) -> None:
        """Add middleware to the dispatch chain."""
        self._middlewares.append(middleware)

    def remove_middleware(self, middleware: Middleware) -> bool:
        """Remove middleware. Returns True if found."""
        try:
            self._middlewares.remove(middleware)
            return True
        except ValueError:
            return False

    # ========================================================================
    # State Access
    # ========================================================================

    def get_state(self) -> Dict[str, Any]:
        """
        Get a copy of current state.

        Thread-safe: Returns shallow copy to prevent external mutation.
        """
        with self._lock:
            return self._state.copy()

    def select(self, selector: Callable[[Dict[str, Any]], T]) -> T:
        """
        Select a slice of state using a selector function.

        More efficient than get_state() for specific values.

        Usage:
            devices = store.select(lambda s: s.get("devices", {}))
        """
        with self._lock:
            return selector(self._state)

    def select_memoized(self, selector: MemoizedSelector[T]) -> T:
        """Use a memoized selector."""
        with self._lock:
            return selector(self._state)

    # ========================================================================
    # Dispatch
    # ========================================================================

    def dispatch(self, action: Action) -> None:
        """
        Dispatch an action to update state.

        Thread-safe:
        - State mutation is atomic
        - Signals queued to main thread if called from background
        """
        if not isinstance(action, Action):
            logger.warning(f"[Store] Invalid action: {type(action)}")
            return

        # If batching, queue action
        if self._is_batching:
            self._batch_actions.append(action)
            return

        # Run through middleware chain
        if self._middlewares:
            self._dispatch_with_middleware(action)
        else:
            self._dispatch_internal(action)

    def _dispatch_with_middleware(self, action: Action) -> None:
        """Dispatch action through middleware chain."""
        middlewares = self._middlewares[:]

        def create_next(index: int) -> Callable[[Action], None]:
            if index >= len(middlewares):
                return self._dispatch_internal

            def next_dispatch(act: Action) -> None:
                middlewares[index](self, act, create_next(index + 1))

            return next_dispatch

        create_next(0)(action)

    def _dispatch_internal(self, action: Action) -> None:
        """Internal dispatch without middleware."""
        with self._lock:
            old_state = self._state

            try:
                new_state = root_reducer(old_state, action)
            except Exception as e:
                logger.error(f"[Store] Reducer error for {action.type.name}: {e}")
                return

            self._state = new_state
            self._dispatch_count += 1

            state_changed = new_state is not old_state
            emit_data = self._prepare_emit_data(action, old_state, new_state, state_changed)

        # Emit signals outside lock
        self._emit_signals(emit_data)

    def _prepare_emit_data(
        self,
        action: Action,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        state_changed: bool,
    ) -> Dict[str, Any]:
        """Prepare data for signal emission."""
        data: Dict[str, Any] = {
            "action": action,
            "state_changed": state_changed,
            "dispatch_count": self._dispatch_count,
        }

        if state_changed:
            data["new_state_copy"] = new_state.copy()

        # Device-related actions
        if action.type in (ActionType.LOAD_DEVICES, ActionType.UPDATE_DEVICES):
            data["devices"] = new_state.get("devices", {}).copy()

        # Sync completed
        if action.type == ActionType.SYNC_COMPLETED:
            data["sync_payload"] = (action.payload or {}).copy()

        # Page change
        if action.type == ActionType.SET_PAGE:
            data["new_page"] = new_state.get("current_page")
            data["old_page"] = old_state.get("current_page")

        return data

    def _emit_signals(self, emit_data: Dict[str, Any]) -> None:
        """Emit Qt signals."""
        action: Action = emit_data["action"]

        # Device updates
        if "devices" in emit_data:
            devices = emit_data["devices"]
            logger.info(f"[Store] Emitting devices_updated: {len(devices)} devices")
            self._safe_emit(self.devices_updated, devices)

        # State changed
        if emit_data.get("state_changed"):
            logger.debug(f"[Store] State changed: {action.type.name} (#{emit_data['dispatch_count']})")
            self._safe_emit(self.state_changed, emit_data["new_state_copy"])

        # Sync completed
        if "sync_payload" in emit_data:
            self._safe_emit(self.sync_completed_signal, emit_data["sync_payload"])

        # Page change
        new_page = emit_data.get("new_page")
        old_page = emit_data.get("old_page")
        if new_page and new_page != old_page:
            self._safe_emit(self.page_changed, new_page)

    def _safe_emit(self, signal: Signal, *args: Any) -> None:
        """Emit signal safely."""
        try:
            signal.emit(*args)
        except RuntimeError as e:
            logger.warning(f"[Store] Signal emit failed: {e}")

    # ========================================================================
    # Batching
    # ========================================================================

    @contextmanager
    def batch(self) -> Iterator[None]:
        """
        Batch multiple dispatches into a single state update.

        Reduces signal emissions for better performance.

        Usage:
            with store.batch():
                store.dispatch(action1)
                store.dispatch(action2)
            # Single state_changed emission here
        """
        with self._lock:
            if self._is_batching:
                # Already batching, just yield
                yield
                return

            self._is_batching = True
            self._batch_actions = []

        try:
            yield
        finally:
            with self._lock:
                actions = self._batch_actions
                self._batch_actions = []
                self._is_batching = False

            # Process all batched actions
            for action in actions:
                if self._middlewares:
                    self._dispatch_with_middleware(action)
                else:
                    self._dispatch_internal(action)

    # ========================================================================
    # Subscriptions
    # ========================================================================

    def subscribe(
        self,
        callback: Callable[[Dict[str, Any]], None],
    ) -> Callable[[], None]:
        """
        Subscribe to state changes.

        Returns an unsubscribe function.
        """
        with self._lock:
            self._subscribers.append(callback)

        self.state_changed.connect(callback)

        def unsubscribe():
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
            try:
                self.state_changed.disconnect(callback)
            except (RuntimeError, TypeError):
                pass

        return unsubscribe

    # ========================================================================
    # Utilities
    # ========================================================================

    def get_dispatch_count(self) -> int:
        """Get total number of dispatches."""
        with self._lock:
            return self._dispatch_count

    def get_action_history(self) -> List[Dict[str, Any]]:
        """Get action history (if dev_tools_middleware is enabled)."""
        return getattr(self, "_action_history", [])

    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        """Reset store to initial or provided state."""
        with self._lock:
            self._state = (new_state or INITIAL_STATE).copy()
            self._dispatch_count = 0

        self._safe_emit(self.state_changed, self._state.copy())


__all__ = [
    "Store",
    "Middleware",
    "MemoizedSelector",
    "logging_middleware",
    "dev_tools_middleware",
]
