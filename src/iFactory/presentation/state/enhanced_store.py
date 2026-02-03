# src/presentation/state/enhanced_store.py
"""
Enhanced Redux-like Store with advanced features.

Features:
- Time-travel debugging
- State persistence
- Immutable state snapshots
- Undo/Redo support
- Action replay
- DevTools integration
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, Generic, Iterator, List, Optional, Protocol, TypeVar, Union

from PySide6.QtCore import QObject, Signal, QTimer

from .actions import Action, ActionType
from .reducers import INITIAL_STATE, root_reducer

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# State Snapshot for Time-Travel
# ============================================================================


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot of state at a point in time."""

    state: Dict[str, Any]
    action: Action
    timestamp: datetime = field(default_factory=datetime.now)
    index: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state,
            "action_type": self.action.type.name,
            "action_payload": self.action.payload,
            "timestamp": self.timestamp.isoformat(),
            "index": self.index,
        }


@dataclass
class StateHistory:
    """
    Manages state history for time-travel debugging.

    Features:
    - Fixed-size history buffer
    - Jump to any point
    - Undo/Redo operations
    """

    max_size: int = 100
    snapshots: List[StateSnapshot] = field(default_factory=list)
    current_index: int = -1

    def push(self, snapshot: StateSnapshot) -> None:
        """Add new snapshot, truncating future if we've gone back."""
        # If we're not at the end, truncate future
        if self.current_index < len(self.snapshots) - 1:
            self.snapshots = self.snapshots[: self.current_index + 1]

        # Add new snapshot
        snapshot = StateSnapshot(
            state=snapshot.state,
            action=snapshot.action,
            timestamp=snapshot.timestamp,
            index=len(self.snapshots),
        )
        self.snapshots.append(snapshot)
        self.current_index = len(self.snapshots) - 1

        # Trim if too large
        if len(self.snapshots) > self.max_size:
            trim_count = len(self.snapshots) - self.max_size
            self.snapshots = self.snapshots[trim_count:]
            self.current_index -= trim_count

    def can_undo(self) -> bool:
        return self.current_index > 0

    def can_redo(self) -> bool:
        return self.current_index < len(self.snapshots) - 1

    def undo(self) -> Optional[StateSnapshot]:
        """Go back one step."""
        if not self.can_undo():
            return None
        self.current_index -= 1
        return self.snapshots[self.current_index]

    def redo(self) -> Optional[StateSnapshot]:
        """Go forward one step."""
        if not self.can_redo():
            return None
        self.current_index += 1
        return self.snapshots[self.current_index]

    def jump_to(self, index: int) -> Optional[StateSnapshot]:
        """Jump to specific point in history."""
        if 0 <= index < len(self.snapshots):
            self.current_index = index
            return self.snapshots[index]
        return None

    def current(self) -> Optional[StateSnapshot]:
        if 0 <= self.current_index < len(self.snapshots):
            return self.snapshots[self.current_index]
        return None

    def clear(self) -> None:
        self.snapshots.clear()
        self.current_index = -1


# ============================================================================
# State Persistence
# ============================================================================


class IStatePersistence(Protocol):
    """Protocol for state persistence."""

    def save(self, state: Dict[str, Any]) -> None:
        """Save state to storage."""
        ...

    def load(self) -> Optional[Dict[str, Any]]:
        """Load state from storage."""
        ...

    def clear(self) -> None:
        """Clear persisted state."""
        ...


class LocalStoragePersistence:
    """
    Persist state to local JSON file.

    Features:
    - Automatic debounced saves
    - Atomic writes (temp file + rename)
    - Error recovery
    """

    def __init__(
        self,
        path: Path,
        debounce_ms: int = 1000,
        keys_to_persist: Optional[List[str]] = None,
    ):
        self._path = path
        self._debounce_ms = debounce_ms
        self._keys = keys_to_persist or [
            "theme",
            "sidebar_expanded",
            "data_range_days",
        ]
        self._pending_state: Optional[Dict[str, Any]] = None
        self._save_timer: Optional[QTimer] = None
        self._lock = threading.Lock()

    def save(self, state: Dict[str, Any]) -> None:
        """Schedule debounced save."""
        with self._lock:
            # Filter to only persist specified keys
            self._pending_state = {k: v for k, v in state.items() if k in self._keys}

        # Schedule save (debounced)
        if self._save_timer is None:
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._do_save)

        self._save_timer.start(self._debounce_ms)

    def _do_save(self) -> None:
        """Actually save to file."""
        with self._lock:
            state = self._pending_state
            self._pending_state = None

        if not state:
            return

        try:
            # Write to temp file first
            temp_path = self._path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(state, f, indent=2, default=str)

            # Atomic rename
            temp_path.replace(self._path)
            logger.debug(f"[Persistence] Saved state to {self._path}")

        except Exception as e:
            logger.error(f"[Persistence] Save failed: {e}")

    def load(self) -> Optional[Dict[str, Any]]:
        """Load state from file."""
        if not self._path.exists():
            return None

        try:
            with open(self._path) as f:
                state = json.load(f)
            logger.info(f"[Persistence] Loaded state from {self._path}")
            return state

        except Exception as e:
            logger.error(f"[Persistence] Load failed: {e}")
            return None

    def clear(self) -> None:
        """Delete persisted state."""
        try:
            self._path.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"[Persistence] Clear failed: {e}")


# ============================================================================
# Immutable State Wrapper
# ============================================================================


class ImmutableDict(dict):
    """
    Dictionary that prevents modification after creation.

    Provides protection against accidental state mutation.
    """

    _frozen: bool = False

    def freeze(self) -> "ImmutableDict":
        """Freeze the dictionary."""
        self._frozen = True
        return self

    def _check_frozen(self) -> None:
        if self._frozen:
            raise TypeError("Cannot modify frozen state. Dispatch an action instead.")

    def __setitem__(self, key: Any, value: Any) -> None:
        self._check_frozen()
        super().__setitem__(key, value)

    def __delitem__(self, key: Any) -> None:
        self._check_frozen()
        super().__delitem__(key)

    def clear(self) -> None:
        self._check_frozen()
        super().clear()

    def pop(self, *args) -> Any:
        self._check_frozen()
        return super().pop(*args)

    def popitem(self) -> tuple:
        self._check_frozen()
        return super().popitem()

    def update(self, *args, **kwargs) -> None:
        self._check_frozen()
        super().update(*args, **kwargs)

    def setdefault(self, key: Any, default: Any = None) -> Any:
        self._check_frozen()
        return super().setdefault(key, default)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ImmutableDict":
        """Create frozen ImmutableDict from regular dict."""
        result = cls(d)
        result.freeze()
        return result


# ============================================================================
# Enhanced Middleware
# ============================================================================


class Middleware(Protocol):
    """Protocol for store middleware."""

    def __call__(
        self,
        store: "EnhancedStore",
        action: Action,
        next_dispatch: Callable[[Action], None],
    ) -> None: ...


def performance_middleware(
    store: "EnhancedStore",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware that tracks performance metrics."""
    start = time.perf_counter()

    next_dispatch(action)

    elapsed = (time.perf_counter() - start) * 1000
    store._metrics["total_dispatch_time"] += elapsed
    store._metrics["dispatch_count"] += 1

    if elapsed > 16:  # > 1 frame at 60fps
        logger.warning(f"[Store] Slow dispatch: {action.type.name} took {elapsed:.1f}ms")


def persistence_middleware(
    persistence: IStatePersistence,
) -> Middleware:
    """Create middleware that persists state changes."""

    def middleware(
        store: "EnhancedStore",
        action: Action,
        next_dispatch: Callable[[Action], None],
    ) -> None:
        next_dispatch(action)
        persistence.save(store.get_state())

    return middleware


def action_logger_middleware(
    store: "EnhancedStore",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Detailed action logging middleware."""
    old_state = store.get_state()

    next_dispatch(action)

    new_state = store.get_state()

    # Log only changed keys
    changed_keys = []
    for key in set(old_state.keys()) | set(new_state.keys()):
        if old_state.get(key) != new_state.get(key):
            changed_keys.append(key)

    if changed_keys:
        logger.debug(f"[Store] {action.type.name} changed: {', '.join(changed_keys)}")


# ============================================================================
# Enhanced Store
# ============================================================================


class EnhancedStore(QObject):
    """
    Enhanced Redux-like store with advanced features.

    Features:
    - Time-travel debugging (undo/redo)
    - State persistence
    - Immutable state enforcement
    - Performance metrics
    - Action replay
    - DevTools integration

    Usage:
        store = EnhancedStore(
            enable_time_travel=True,
            persistence=LocalStoragePersistence(Path("state.json")),
        )

        store.dispatch(set_theme("dark"))

        # Time travel
        store.undo()
        store.redo()
        store.jump_to_history(5)

        # DevTools
        history = store.get_action_history()
        store.replay_actions(history[:10])
    """

    # Signals
    state_changed = Signal(dict)
    devices_updated = Signal(dict)
    page_changed = Signal(str)
    undo_available = Signal(bool)
    redo_available = Signal(bool)

    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        middlewares: Optional[List[Middleware]] = None,
        enable_time_travel: bool = False,
        enable_immutable: bool = False,
        persistence: Optional[IStatePersistence] = None,
        history_size: int = 100,
    ):
        super().__init__()

        # Load persisted state or use initial
        persisted = persistence.load() if persistence else None
        base_state = (initial_state or INITIAL_STATE).copy()
        if persisted:
            base_state.update(persisted)

        self._state: Dict[str, Any] = base_state
        self._middlewares: List[Middleware] = middlewares or []
        self._enable_time_travel = enable_time_travel
        self._enable_immutable = enable_immutable
        self._persistence = persistence

        # Time travel
        self._history = StateHistory(max_size=history_size)
        self._is_time_traveling = False

        # Metrics
        self._metrics = {
            "dispatch_count": 0,
            "total_dispatch_time": 0.0,
        }

        # Thread safety
        self._lock = threading.RLock()

        # Batching
        self._is_batching = False
        self._batch_actions: List[Action] = []

        # Add persistence middleware if enabled
        if persistence:
            self._middlewares.append(persistence_middleware(persistence))

        # Initial snapshot
        if enable_time_travel:
            init_action = Action(type=ActionType.INIT)
            self._history.push(
                StateSnapshot(
                    state=self._state.copy(),
                    action=init_action,
                )
            )

        logger.debug(f"[EnhancedStore] Initialized with time_travel={enable_time_travel}")

    # ========================================================================
    # State Access
    # ========================================================================

    def get_state(self) -> Dict[str, Any]:
        """Get current state (immutable if enabled)."""
        with self._lock:
            if self._enable_immutable:
                return ImmutableDict.from_dict(self._state)
            return self._state.copy()

    def select(self, selector: Callable[[Dict[str, Any]], T]) -> T:
        """Select a slice of state."""
        with self._lock:
            return selector(self._state)

    # ========================================================================
    # Dispatch
    # ========================================================================

    def dispatch(self, action: Action) -> None:
        """Dispatch an action to update state."""
        if not isinstance(action, Action):
            logger.warning(f"[Store] Invalid action: {type(action)}")
            return

        if self._is_batching:
            self._batch_actions.append(action)
            return

        # Reset time travel position when new action dispatched
        if self._enable_time_travel and not self._is_time_traveling:
            # If we're not at the end of history, we're starting new branch
            pass

        if self._middlewares:
            self._dispatch_with_middleware(action)
        else:
            self._dispatch_internal(action)

    def _dispatch_with_middleware(self, action: Action) -> None:
        """Dispatch through middleware chain."""
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
                logger.error(f"[Store] Reducer error: {e}")
                return

            self._state = new_state

            # Record in history
            if self._enable_time_travel and not self._is_time_traveling:
                self._history.push(
                    StateSnapshot(
                        state=new_state.copy(),
                        action=action,
                    )
                )

            state_changed = new_state is not old_state

        # Emit signals outside lock
        if state_changed:
            self._emit_signals(action, old_state, new_state)

    def _emit_signals(
        self,
        action: Action,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
    ) -> None:
        """Emit appropriate signals based on action."""
        # General state change
        self.state_changed.emit(new_state.copy())

        # Devices
        if action.type in (ActionType.LOAD_DEVICES, ActionType.UPDATE_DEVICES):
            self.devices_updated.emit(new_state.get("devices", {}))

        # Page change
        if action.type == ActionType.SET_PAGE:
            old_page = old_state.get("current_page")
            new_page = new_state.get("current_page")
            if old_page != new_page:
                self.page_changed.emit(new_page)

        # Undo/Redo availability
        if self._enable_time_travel:
            self.undo_available.emit(self._history.can_undo())
            self.redo_available.emit(self._history.can_redo())

    # ========================================================================
    # Batching
    # ========================================================================

    @contextmanager
    def batch(self) -> Iterator[None]:
        """Batch multiple dispatches."""
        with self._lock:
            if self._is_batching:
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

            for action in actions:
                self.dispatch(action)

    # ========================================================================
    # Time Travel
    # ========================================================================

    def undo(self) -> bool:
        """Undo last action."""
        if not self._enable_time_travel:
            logger.warning("[Store] Time travel not enabled")
            return False

        with self._lock:
            snapshot = self._history.undo()
            if not snapshot:
                return False

            self._is_time_traveling = True
            self._state = snapshot.state.copy()
            self._is_time_traveling = False

        self.state_changed.emit(self._state.copy())
        self.undo_available.emit(self._history.can_undo())
        self.redo_available.emit(self._history.can_redo())

        logger.debug(f"[Store] Undo to index {self._history.current_index}")
        return True

    def redo(self) -> bool:
        """Redo next action."""
        if not self._enable_time_travel:
            return False

        with self._lock:
            snapshot = self._history.redo()
            if not snapshot:
                return False

            self._is_time_traveling = True
            self._state = snapshot.state.copy()
            self._is_time_traveling = False

        self.state_changed.emit(self._state.copy())
        self.undo_available.emit(self._history.can_undo())
        self.redo_available.emit(self._history.can_redo())

        logger.debug(f"[Store] Redo to index {self._history.current_index}")
        return True

    def jump_to_history(self, index: int) -> bool:
        """Jump to specific point in history."""
        if not self._enable_time_travel:
            return False

        with self._lock:
            snapshot = self._history.jump_to(index)
            if not snapshot:
                return False

            self._is_time_traveling = True
            self._state = snapshot.state.copy()
            self._is_time_traveling = False

        self.state_changed.emit(self._state.copy())
        logger.debug(f"[Store] Jumped to history index {index}")
        return True

    def get_history(self) -> List[Dict[str, Any]]:
        """Get history for DevTools."""
        return [s.to_dict() for s in self._history.snapshots]

    def get_history_index(self) -> int:
        """Get current history index."""
        return self._history.current_index

    # ========================================================================
    # Action Replay
    # ========================================================================

    def replay_actions(self, actions: List[Action]) -> None:
        """Replay a sequence of actions."""
        logger.info(f"[Store] Replaying {len(actions)} actions")

        # Reset to initial state
        self.reset()

        # Replay each action
        for action in actions:
            self.dispatch(action)

    # ========================================================================
    # Metrics & DevTools
    # ========================================================================

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        avg_time = 0.0
        if self._metrics["dispatch_count"] > 0:
            avg_time = self._metrics["total_dispatch_time"] / self._metrics["dispatch_count"]

        return {
            **self._metrics,
            "avg_dispatch_time_ms": avg_time,
            "history_size": len(self._history.snapshots),
            "current_history_index": self._history.current_index,
        }

    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        """Reset store to initial state."""
        with self._lock:
            self._state = (new_state or INITIAL_STATE).copy()
            self._history.clear()
            self._metrics = {
                "dispatch_count": 0,
                "total_dispatch_time": 0.0,
            }

        self.state_changed.emit(self._state.copy())


__all__ = [
    "EnhancedStore",
    "StateSnapshot",
    "StateHistory",
    "IStatePersistence",
    "LocalStoragePersistence",
    "ImmutableDict",
    "performance_middleware",
    "persistence_middleware",
    "action_logger_middleware",
]
