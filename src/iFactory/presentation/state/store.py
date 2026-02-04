# src/iFactory/presentation/state/store.py
"""
Unified Redux-like Store.

Combines features from both Store and EnhancedStore into a single,
configurable implementation.

Features:
- Thread-safe state updates
- Qt signal integration
- Middleware pipeline
- Optional time-travel debugging
- Optional state persistence
- Batched updates
- Memoized selectors
- Both AppState and dict support
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
    Union,
    overload,
)

from PySide6.QtCore import QObject, Signal, QTimer

from .types import AppState, create_initial_state
from .actions import Action, ActionType
from .reducers import root_reducer, root_reducer_dict, INITIAL_STATE_DICT

logger = logging.getLogger(__name__)

T = TypeVar("T")
S = TypeVar("S")


# ============================================================================
# Protocols
# ============================================================================


class Middleware(Protocol):
    """Protocol for store middleware."""

    def __call__(
        self,
        store: "Store",
        action: Action,
        next_dispatch: Callable[[Action], None],
    ) -> None:
        """Process action and call next middleware."""
        ...


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


# ============================================================================
# Middleware Implementations
# ============================================================================


def logging_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware that logs all actions with timing."""
    start = time.perf_counter()

    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(f"[Store] Dispatching: {action.type.name}")

    next_dispatch(action)

    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > 16:  # > 1 frame at 60fps
        logger.warning(f"[Store] Slow dispatch: {action.type.name} took {elapsed_ms:.1f}ms")


def performance_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware that tracks performance metrics."""
    start = time.perf_counter()

    next_dispatch(action)

    elapsed = (time.perf_counter() - start) * 1000

    # Update store metrics
    if hasattr(store, "_metrics"):
        store._metrics["total_dispatch_time"] += elapsed
        store._metrics["dispatch_count"] += 1
        store._metrics["max_dispatch_time"] = max(
            store._metrics.get("max_dispatch_time", 0),
            elapsed,
        )


def dev_tools_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware for Redux DevTools integration."""
    if not hasattr(store, "_action_history"):
        store._action_history = []

    store._action_history.append(
        {
            "action": action.type.name,
            "payload": _serialize_payload(action.payload),
            "timestamp": datetime.now().isoformat(),
        }
    )

    # Keep last 100 actions
    if len(store._action_history) > 100:
        store._action_history = store._action_history[-100:]

    next_dispatch(action)


def _serialize_payload(payload: Any) -> Any:
    """Serialize payload for logging/debugging."""
    if payload is None:
        return None
    if isinstance(payload, (str, int, float, bool)):
        return payload
    if isinstance(payload, dict):
        return {k: _serialize_payload(v) for k, v in payload.items()}
    if isinstance(payload, (list, tuple)):
        return [_serialize_payload(v) for v in payload]
    if hasattr(payload, "__dataclass_fields__"):
        return {field: _serialize_payload(getattr(payload, field)) for field in payload.__dataclass_fields__}
    return str(type(payload).__name__)


def create_persistence_middleware(
    persistence: IStatePersistence,
) -> Middleware:
    """Create middleware that persists state changes."""

    def middleware(
        store: "Store",
        action: Action,
        next_dispatch: Callable[[Action], None],
    ) -> None:
        next_dispatch(action)

        # Persist after state change
        state_dict = store.get_state_dict()
        persistence.save(state_dict)

    return middleware


# ============================================================================
# State Persistence Implementations
# ============================================================================


class LocalStoragePersistence:
    """
    Persist state to local JSON file.

    Features:
    - Debounced saves to reduce I/O
    - Atomic writes via temp file
    - Configurable keys to persist
    """

    def __init__(
        self,
        path: Path,
        debounce_ms: int = 1000,
        keys_to_persist: Optional[List[str]] = None,
    ):
        self._path = Path(path)
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

        # Schedule save
        if self._save_timer is None:
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._do_save)

        self._save_timer.start(self._debounce_ms)

    def _do_save(self) -> None:
        """Actually write to file."""
        with self._lock:
            state = self._pending_state
            self._pending_state = None

        if not state:
            return

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)

            # Write to temp file first
            temp_path = self._path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
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
            with open(self._path, "r", encoding="utf-8") as f:
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
# Time Travel Support
# ============================================================================


@dataclass(frozen=True)
class StateSnapshot:
    """Immutable snapshot for time-travel."""

    state: Dict[str, Any]
    action: Action
    timestamp: datetime = field(default_factory=datetime.now)
    index: int = 0


@dataclass
class StateHistory:
    """Manages state history for undo/redo."""

    max_size: int = 100
    _snapshots: List[StateSnapshot] = field(default_factory=list)
    _current_index: int = -1

    def push(self, state: Dict[str, Any], action: Action) -> None:
        """Add new snapshot."""
        # Truncate future if we've gone back
        if self._current_index < len(self._snapshots) - 1:
            self._snapshots = self._snapshots[: self._current_index + 1]

        snapshot = StateSnapshot(
            state=copy.deepcopy(state),
            action=action,
            index=len(self._snapshots),
        )
        self._snapshots.append(snapshot)
        self._current_index = len(self._snapshots) - 1

        # Trim if too large
        if len(self._snapshots) > self.max_size:
            trim = len(self._snapshots) - self.max_size
            self._snapshots = self._snapshots[trim:]
            self._current_index -= trim

    def can_undo(self) -> bool:
        return self._current_index > 0

    def can_redo(self) -> bool:
        return self._current_index < len(self._snapshots) - 1

    def undo(self) -> Optional[StateSnapshot]:
        if not self.can_undo():
            return None
        self._current_index -= 1
        return self._snapshots[self._current_index]

    def redo(self) -> Optional[StateSnapshot]:
        if not self.can_redo():
            return None
        self._current_index += 1
        return self._snapshots[self._current_index]

    def jump_to(self, index: int) -> Optional[StateSnapshot]:
        if 0 <= index < len(self._snapshots):
            self._current_index = index
            return self._snapshots[index]
        return None

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def snapshots(self) -> List[StateSnapshot]:
        return self._snapshots.copy()

    def clear(self) -> None:
        self._snapshots.clear()
        self._current_index = -1


# ============================================================================
# Store Configuration
# ============================================================================


@dataclass
class StoreConfig:
    """Configuration for Store behavior."""

    # Use typed AppState or dict
    use_typed_state: bool = False

    # Time travel
    enable_time_travel: bool = False
    history_size: int = 100

    # Persistence
    persistence: Optional[IStatePersistence] = None

    # Default middlewares
    enable_logging: bool = True
    enable_performance_tracking: bool = False
    enable_dev_tools: bool = False


# ============================================================================
# Main Store Class
# ============================================================================


class Store(QObject):
    """
    Central state store with Qt signal integration.

    Thread-safety:
    - State access protected by RLock
    - Signals emitted safely

    Usage:
        # Basic usage
        store = Store()
        store.dispatch(set_page("electrode"))
        state = store.get_state()

        # With configuration
        store = Store(config=StoreConfig(
            enable_time_travel=True,
            persistence=LocalStoragePersistence(Path("state.json")),
        ))

        # Subscriptions
        unsubscribe = store.subscribe(lambda state: print(state))
        unsubscribe()  # When done
    """

    # Qt signals for UI updates
    state_changed = Signal(dict)
    devices_updated = Signal(dict)
    page_changed = Signal(str)
    sync_completed_signal = Signal(dict)

    # Time travel signals
    undo_available = Signal(bool)
    redo_available = Signal(bool)

    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        middlewares: Optional[List[Middleware]] = None,
        config: Optional[StoreConfig] = None,
    ):
        super().__init__()

        self._config = config or StoreConfig()

        # Load persisted state if available
        base_state = (initial_state or INITIAL_STATE_DICT).copy()
        if self._config.persistence:
            persisted = self._config.persistence.load()
            if persisted:
                base_state.update(persisted)

        # State storage (always dict for now)
        self._state: Dict[str, Any] = base_state

        # Middleware pipeline
        self._middlewares: List[Middleware] = []
        self._setup_middlewares(middlewares or [])

        # Subscribers
        self._subscribers: List[Callable[[Dict[str, Any]], None]] = []

        # Batching
        self._is_batching = False
        self._batch_actions: List[Action] = []

        # Time travel
        self._history: Optional[StateHistory] = None
        self._is_time_traveling = False
        if self._config.enable_time_travel:
            self._history = StateHistory(max_size=self._config.history_size)
            # Initial snapshot
            init_action = Action(type=ActionType.INIT)
            self._history.push(self._state.copy(), init_action)

        # Metrics
        self._metrics: Dict[str, Any] = {
            "dispatch_count": 0,
            "total_dispatch_time": 0.0,
            "max_dispatch_time": 0.0,
        }

        # Thread safety
        self._lock = threading.RLock()

        logger.debug(f"[Store] Initialized with {len(self._state)} state keys, " f"time_travel={self._config.enable_time_travel}")

    def _setup_middlewares(self, custom_middlewares: List[Middleware]) -> None:
        """Setup middleware pipeline."""
        # Add configured default middlewares
        if self._config.enable_logging:
            self._middlewares.append(logging_middleware)

        if self._config.enable_performance_tracking:
            self._middlewares.append(performance_middleware)

        if self._config.enable_dev_tools:
            self._middlewares.append(dev_tools_middleware)

        if self._config.persistence:
            self._middlewares.append(create_persistence_middleware(self._config.persistence))

        # Add custom middlewares
        self._middlewares.extend(custom_middlewares)

    # ========================================================================
    # Middleware Management
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

        Thread-safe: Returns shallow copy.
        """
        with self._lock:
            return self._state.copy()

    def get_state_dict(self) -> Dict[str, Any]:
        """Alias for get_state() for clarity."""
        return self.get_state()

    def select(self, selector: Callable[[Dict[str, Any]], T]) -> T:
        """
        Select a slice of state using a selector function.

        Usage:
            devices = store.select(lambda s: s.get("devices", {}))
        """
        with self._lock:
            return selector(self._state)

    # ========================================================================
    # Dispatch
    # ========================================================================

    def dispatch(self, action: Action) -> None:
        """
        Dispatch an action to update state.

        Thread-safe with proper signal emission.
        """
        if not isinstance(action, Action):
            logger.warning(f"[Store] Invalid action type: {type(action)}")
            return

        # Queue if batching
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
                # Use dict reducer
                new_state = root_reducer_dict(old_state, action)
            except Exception as e:
                logger.error(f"[Store] Reducer error for {action.type.name}: {e}")
                return

            self._state = new_state
            self._metrics["dispatch_count"] += 1

            # Record in history
            if self._history and not self._is_time_traveling:
                self._history.push(new_state.copy(), action)

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
        }

        if state_changed:
            data["new_state_copy"] = new_state.copy()

        # Device updates
        if action.type in (ActionType.LOAD_DEVICES, ActionType.UPDATE_DEVICES):
            data["devices"] = new_state.get("devices", {}).copy()

        # Page change
        if action.type == ActionType.SET_PAGE:
            data["new_page"] = new_state.get("current_page")
            data["old_page"] = old_state.get("current_page")

        # Sync completed
        if action.type == ActionType.SYNC_COMPLETED:
            data["sync_payload"] = action.payload or {}

        return data

    def _emit_signals(self, emit_data: Dict[str, Any]) -> None:
        """Emit Qt signals based on action results."""
        action: Action = emit_data["action"]

        # Device updates
        if "devices" in emit_data:
            self._safe_emit(self.devices_updated, emit_data["devices"])

        # State changed
        if emit_data.get("state_changed"):
            self._safe_emit(self.state_changed, emit_data["new_state_copy"])

        # Page change
        new_page = emit_data.get("new_page")
        old_page = emit_data.get("old_page")
        if new_page and new_page != old_page:
            self._safe_emit(self.page_changed, new_page)

        # Sync completed
        if "sync_payload" in emit_data:
            self._safe_emit(self.sync_completed_signal, emit_data["sync_payload"])

        # Time travel availability
        if self._history:
            self._safe_emit(self.undo_available, self._history.can_undo())
            self._safe_emit(self.redo_available, self._history.can_redo())

    def _safe_emit(self, signal: Signal, *args: Any) -> None:
        """Emit signal safely, catching disconnected errors."""
        try:
            signal.emit(*args)
        except RuntimeError as e:
            logger.debug(f"[Store] Signal emit skipped: {e}")

    # ========================================================================
    # Batching
    # ========================================================================

    @contextmanager
    def batch(self) -> Iterator[None]:
        """
        Batch multiple dispatches into single state update.

        Usage:
            with store.batch():
                store.dispatch(action1)
                store.dispatch(action2)
            # Single state_changed emission
        """
        with self._lock:
            if self._is_batching:
                # Already batching
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

            # Process batched actions
            for action in actions:
                if self._middlewares:
                    self._dispatch_with_middleware(action)
                else:
                    self._dispatch_internal(action)

    # ========================================================================
    # Time Travel
    # ========================================================================

    def undo(self) -> bool:
        """Undo last action. Returns True if successful."""
        if not self._history:
            logger.warning("[Store] Time travel not enabled")
            return False

        with self._lock:
            snapshot = self._history.undo()
            if not snapshot:
                return False

            self._is_time_traveling = True
            self._state = snapshot.state.copy()
            self._is_time_traveling = False

        self._safe_emit(self.state_changed, self._state.copy())
        self._safe_emit(self.undo_available, self._history.can_undo())
        self._safe_emit(self.redo_available, self._history.can_redo())

        logger.debug(f"[Store] Undo to index {self._history.current_index}")
        return True

    def redo(self) -> bool:
        """Redo next action. Returns True if successful."""
        if not self._history:
            return False

        with self._lock:
            snapshot = self._history.redo()
            if not snapshot:
                return False

            self._is_time_traveling = True
            self._state = snapshot.state.copy()
            self._is_time_traveling = False

        self._safe_emit(self.state_changed, self._state.copy())
        self._safe_emit(self.undo_available, self._history.can_undo())
        self._safe_emit(self.redo_available, self._history.can_redo())

        logger.debug(f"[Store] Redo to index {self._history.current_index}")
        return True

    def jump_to_history(self, index: int) -> bool:
        """Jump to specific history index."""
        if not self._history:
            return False

        with self._lock:
            snapshot = self._history.jump_to(index)
            if not snapshot:
                return False

            self._is_time_traveling = True
            self._state = snapshot.state.copy()
            self._is_time_traveling = False

        self._safe_emit(self.state_changed, self._state.copy())
        logger.debug(f"[Store] Jumped to history index {index}")
        return True

    def can_undo(self) -> bool:
        """Check if undo is available."""
        return self._history.can_undo() if self._history else False

    def can_redo(self) -> bool:
        """Check if redo is available."""
        return self._history.can_redo() if self._history else False

    def get_history(self) -> List[Dict[str, Any]]:
        """Get action history for DevTools."""
        if not self._history:
            return []
        return [
            {
                "index": s.index,
                "action": s.action.type.name,
                "timestamp": s.timestamp.isoformat(),
            }
            for s in self._history.snapshots
        ]

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

        def unsubscribe() -> None:
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
        """Get total dispatch count."""
        with self._lock:
            return self._metrics["dispatch_count"]

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics."""
        with self._lock:
            dispatch_count = self._metrics["dispatch_count"]
            total_time = self._metrics["total_dispatch_time"]

            return {
                **self._metrics,
                "avg_dispatch_time_ms": (total_time / dispatch_count if dispatch_count > 0 else 0),
                "history_size": (len(self._history.snapshots) if self._history else 0),
            }

    def get_action_history(self) -> List[Dict[str, Any]]:
        """Get action history (from dev_tools_middleware)."""
        return getattr(self, "_action_history", [])

    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        """Reset store to initial or provided state."""
        with self._lock:
            self._state = (new_state or INITIAL_STATE_DICT).copy()
            self._metrics = {
                "dispatch_count": 0,
                "total_dispatch_time": 0.0,
                "max_dispatch_time": 0.0,
            }
            if self._history:
                self._history.clear()

        self._safe_emit(self.state_changed, self._state.copy())


# ============================================================================
# Convenience alias
# ============================================================================

EnhancedStore = Store  # EnhancedStore is now just Store with config


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Store
    "Store",
    "EnhancedStore",
    "StoreConfig",
    # Protocols
    "Middleware",
    "IStatePersistence",
    # Middleware
    "logging_middleware",
    "performance_middleware",
    "dev_tools_middleware",
    "create_persistence_middleware",
    # Persistence
    "LocalStoragePersistence",
    # Time travel
    "StateSnapshot",
    "StateHistory",
]
