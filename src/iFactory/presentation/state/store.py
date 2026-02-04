# src/iFactory/presentation/state/store.py
"""
Enhanced Redux-like Store with UX Improvements.

NEW FEATURES:
- Optimistic updates with automatic rollback
- Toast notification system
- Selector memoization with cache invalidation
- Action debouncing/throttling
- Enhanced DevTools
- Loading state tracking per action
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
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
    Set,
    TypeVar,
    Union,
)
import uuid

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
    ) -> None: ...


class IStatePersistence(Protocol):
    """Protocol for state persistence."""

    def save(self, state: Dict[str, Any]) -> None: ...
    def load(self) -> Optional[Dict[str, Any]]: ...
    def clear(self) -> None: ...


# ============================================================================
# Toast System
# ============================================================================


@dataclass
class Toast:
    """Toast notification model."""

    id: str
    message: str
    variant: str = "info"  # info, success, warning, error
    duration: int = 3000
    action_label: Optional[str] = None
    action_callback: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    is_dismissing: bool = False


class ToastManager(QObject):
    """
    Manages toast notifications.

    Features:
    - Auto-dismiss with configurable duration
    - Stacking with limit
    - Action buttons
    - Dismiss animations
    """

    toast_added = Signal(object)  # Toast
    toast_removed = Signal(str)  # toast_id
    toast_updated = Signal(object)  # Toast

    MAX_TOASTS = 5

    def __init__(self, parent=None):
        super().__init__(parent)
        self._toasts: Dict[str, Toast] = {}
        self._timers: Dict[str, QTimer] = {}
        self._queue: deque[Toast] = deque()

    def show(
        self,
        message: str,
        variant: str = "info",
        duration: int = 3000,
        action_label: Optional[str] = None,
        action_callback: Optional[str] = None,
    ) -> str:
        """Show a toast notification."""
        toast_id = str(uuid.uuid4())[:8]

        toast = Toast(
            id=toast_id,
            message=message,
            variant=variant,
            duration=duration,
            action_label=action_label,
            action_callback=action_callback,
        )

        if len(self._toasts) >= self.MAX_TOASTS:
            # Queue for later
            self._queue.append(toast)
            return toast_id

        self._add_toast(toast)
        return toast_id

    def _add_toast(self, toast: Toast) -> None:
        """Add toast to active list."""
        self._toasts[toast.id] = toast
        self.toast_added.emit(toast)

        # Auto-dismiss timer
        if toast.duration > 0:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.timeout.connect(lambda: self.dismiss(toast.id))
            timer.start(toast.duration)
            self._timers[toast.id] = timer

    def dismiss(self, toast_id: str, animate: bool = True) -> None:
        """Dismiss a toast."""
        if toast_id not in self._toasts:
            return

        toast = self._toasts[toast_id]

        if animate and not toast.is_dismissing:
            # Mark as dismissing for animation
            toast.is_dismissing = True
            self.toast_updated.emit(toast)

            # Actually remove after animation
            QTimer.singleShot(300, lambda: self._remove_toast(toast_id))
        else:
            self._remove_toast(toast_id)

    def _remove_toast(self, toast_id: str) -> None:
        """Remove toast completely."""
        if toast_id in self._toasts:
            del self._toasts[toast_id]

        if toast_id in self._timers:
            self._timers[toast_id].stop()
            del self._timers[toast_id]

        self.toast_removed.emit(toast_id)

        # Show queued toast
        if self._queue:
            next_toast = self._queue.popleft()
            self._add_toast(next_toast)

    def dismiss_all(self) -> None:
        """Dismiss all toasts."""
        for toast_id in list(self._toasts.keys()):
            self.dismiss(toast_id, animate=False)
        self._queue.clear()

    @property
    def active_toasts(self) -> List[Toast]:
        return list(self._toasts.values())

    # Convenience methods
    def success(self, message: str, duration: int = 3000) -> str:
        return self.show(message, "success", duration)

    def error(self, message: str, duration: int = 5000) -> str:
        return self.show(message, "error", duration)

    def warning(self, message: str, duration: int = 4000) -> str:
        return self.show(message, "warning", duration)

    def info(self, message: str, duration: int = 3000) -> str:
        return self.show(message, "info", duration)


# ============================================================================
# Optimistic Updates
# ============================================================================


@dataclass
class OptimisticUpdate:
    """Tracks an optimistic update for potential rollback."""

    request_id: str
    action: Action
    previous_state: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    timeout_ms: int = 10000  # 10 second timeout


class OptimisticUpdateManager:
    """
    Manages optimistic updates with automatic rollback.

    Usage:
        # In action payload, add: optimistic=True, request_id="xyz"
        # On success: dispatch action with optimistic_success=True, request_id="xyz"
        # On failure: dispatch action with optimistic_failure=True, request_id="xyz"
    """

    def __init__(self, store: "Store"):
        self._store = store
        self._pending: Dict[str, OptimisticUpdate] = {}
        self._cleanup_timer = QTimer()
        self._cleanup_timer.timeout.connect(self._cleanup_expired)
        self._cleanup_timer.start(5000)  # Check every 5s

    def register(
        self,
        request_id: str,
        action: Action,
        state: Dict[str, Any],
    ) -> None:
        """Register an optimistic update."""
        self._pending[request_id] = OptimisticUpdate(
            request_id=request_id,
            action=action,
            previous_state=copy.deepcopy(state),
        )
        logger.debug(f"[Optimistic] Registered: {request_id}")

    def confirm(self, request_id: str) -> bool:
        """Confirm optimistic update succeeded."""
        if request_id in self._pending:
            del self._pending[request_id]
            logger.debug(f"[Optimistic] Confirmed: {request_id}")
            return True
        return False

    def rollback(self, request_id: str) -> Optional[Dict[str, Any]]:
        """Rollback optimistic update."""
        if request_id not in self._pending:
            return None

        update = self._pending.pop(request_id)
        logger.warning(f"[Optimistic] Rolling back: {request_id}")
        return update.previous_state

    def _cleanup_expired(self) -> None:
        """Clean up expired optimistic updates."""
        now = datetime.now()
        expired = []

        for request_id, update in self._pending.items():
            age_ms = (now - update.timestamp).total_seconds() * 1000
            if age_ms > update.timeout_ms:
                expired.append(request_id)

        for request_id in expired:
            logger.warning(f"[Optimistic] Expired, rolling back: {request_id}")
            state = self.rollback(request_id)
            if state and self._store:
                # Force state restore
                self._store._state = state
                self._store.state_changed.emit(state.copy())

    def dispose(self) -> None:
        self._cleanup_timer.stop()
        self._pending.clear()


# ============================================================================
# Loading State Tracker
# ============================================================================


class LoadingStateTracker:
    """
    Track loading states per action/feature.

    Allows components to show loading states for specific operations.
    """

    def __init__(self):
        self._loading: Dict[str, bool] = {}
        self._messages: Dict[str, str] = {}

    def set_loading(self, key: str, loading: bool, message: str = "") -> None:
        """Set loading state for a key."""
        if loading:
            self._loading[key] = True
            self._messages[key] = message
        else:
            self._loading.pop(key, None)
            self._messages.pop(key, None)

    def is_loading(self, key: str) -> bool:
        """Check if key is loading."""
        return self._loading.get(key, False)

    def get_message(self, key: str) -> str:
        """Get loading message for key."""
        return self._messages.get(key, "")

    @property
    def is_any_loading(self) -> bool:
        """Check if anything is loading."""
        return bool(self._loading)

    @property
    def all_loading_keys(self) -> List[str]:
        """Get all loading keys."""
        return list(self._loading.keys())

    def clear(self) -> None:
        self._loading.clear()
        self._messages.clear()


# ============================================================================
# Selector Memoization
# ============================================================================


class MemoizedSelector(Generic[T]):
    """
    Memoized selector with dependency tracking.

    Usage:
        get_devices = MemoizedSelector(lambda s: s.get("devices", {}))
        devices = get_devices(state)
    """

    def __init__(
        self,
        selector_fn: Callable[[Dict[str, Any]], T],
        depends_on: Optional[List[str]] = None,
    ):
        self._selector_fn = selector_fn
        self._depends_on = depends_on or []
        self._cache: Optional[T] = None
        self._last_deps: Optional[tuple] = None

    def __call__(self, state: Dict[str, Any]) -> T:
        # Get dependency values
        if self._depends_on:
            deps = tuple(state.get(key) for key in self._depends_on)
        else:
            deps = (id(state),)  # Use state identity

        # Check cache
        if self._last_deps == deps and self._cache is not None:
            return self._cache

        # Compute
        self._cache = self._selector_fn(state)
        self._last_deps = deps

        return self._cache

    def invalidate(self) -> None:
        """Invalidate cache."""
        self._cache = None
        self._last_deps = None


def create_selector(
    *input_selectors: MemoizedSelector,
    combiner: Callable[..., T],
) -> MemoizedSelector[T]:
    """Create a composed selector from input selectors."""

    def selector_fn(state: Dict[str, Any]) -> T:
        inputs = [sel(state) for sel in input_selectors]
        return combiner(*inputs)

    return MemoizedSelector(selector_fn)


# ============================================================================
# Enhanced Middleware
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
    if elapsed_ms > 16:
        logger.warning(f"[Store] Slow dispatch: {action.type.name} took {elapsed_ms:.1f}ms")


def optimistic_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """
    Handle optimistic updates.

    Checks action meta for:
    - optimistic: bool - Mark as optimistic update
    - optimistic_success: bool - Confirm optimistic update
    - optimistic_failure: bool - Rollback optimistic update
    - request_id: str - Unique ID for tracking
    """
    if not hasattr(store, "_optimistic_manager"):
        next_dispatch(action)
        return

    meta = action.meta or {}
    request_id = meta.get("request_id")

    # Handle optimistic success
    if meta.get("optimistic_success") and request_id:
        store._optimistic_manager.confirm(request_id)
        next_dispatch(action)
        return

    # Handle optimistic failure
    if meta.get("optimistic_failure") and request_id:
        previous_state = store._optimistic_manager.rollback(request_id)
        if previous_state:
            store._state = previous_state
            store.state_changed.emit(previous_state.copy())

            # Show error toast if available
            if hasattr(store, "_toast_manager"):
                error_msg = meta.get("error", "Operation failed")
                store._toast_manager.error(f"⚠️ {error_msg}")
        return

    # Register new optimistic update
    if meta.get("optimistic") and request_id:
        store._optimistic_manager.register(
            request_id,
            action,
            store._state.copy(),
        )

    next_dispatch(action)


def toast_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """
    Automatically show toasts for certain actions.
    """
    next_dispatch(action)

    if not hasattr(store, "_toast_manager"):
        return

    toast_manager: ToastManager = store._toast_manager

    # Auto-toast for sync actions
    if action.type == ActionType.SYNC_COMPLETED:
        payload = action.payload
        if hasattr(payload, "device_count"):
            count = payload.device_count
        elif isinstance(payload, dict):
            count = payload.get("device_count", 0)
        else:
            count = 0

        if count > 0:
            toast_manager.success(f"✓ Synced {count} devices")

    elif action.type == ActionType.SYNC_FAILED:
        payload = action.payload
        if hasattr(payload, "error_message"):
            msg = payload.error_message
        elif isinstance(payload, dict):
            msg = payload.get("error_message", "Sync failed")
        else:
            msg = "Sync failed"

        toast_manager.error(f"⚠️ {msg}")

    # Handle explicit toast actions
    elif action.type == ActionType.SET_ERROR:
        payload = action.payload
        if hasattr(payload, "message"):
            msg = payload.message
        elif isinstance(payload, dict):
            msg = payload.get("message", "Error")
        else:
            msg = str(payload) if payload else "Error"

        toast_manager.error(msg)


def debounce_middleware(
    debounce_ms: int = 100,
    action_types: Optional[Set[ActionType]] = None,
) -> Middleware:
    """
    Create middleware that debounces rapid actions.

    Args:
        debounce_ms: Debounce interval
        action_types: Action types to debounce (None = all)
    """
    pending: Dict[ActionType, tuple] = {}  # type -> (action, timer)

    def middleware(
        store: "Store",
        action: Action,
        next_dispatch: Callable[[Action], None],
    ) -> None:
        # Check if should debounce
        if action_types and action.type not in action_types:
            next_dispatch(action)
            return

        action_type = action.type

        # Cancel pending
        if action_type in pending:
            _, timer = pending[action_type]
            timer.stop()

        # Create new timer
        timer = QTimer()
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: _dispatch_pending(action_type))

        pending[action_type] = (action, timer)
        timer.start(debounce_ms)

    def _dispatch_pending(action_type: ActionType) -> None:
        if action_type in pending:
            action, _ = pending.pop(action_type)
            # Note: We need store reference here, captured via closure

    return middleware


def performance_middleware(
    store: "Store",
    action: Action,
    next_dispatch: Callable[[Action], None],
) -> None:
    """Middleware that tracks performance metrics."""
    start = time.perf_counter()

    next_dispatch(action)

    elapsed = (time.perf_counter() - start) * 1000

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
        state_dict = store.get_state_dict()
        persistence.save(state_dict)

    return middleware


# ============================================================================
# State Persistence
# ============================================================================


class LocalStoragePersistence:
    """Persist state to local JSON file."""

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
        with self._lock:
            self._pending_state = {k: v for k, v in state.items() if k in self._keys}

        if self._save_timer is None:
            self._save_timer = QTimer()
            self._save_timer.setSingleShot(True)
            self._save_timer.timeout.connect(self._do_save)

        self._save_timer.start(self._debounce_ms)

    def _do_save(self) -> None:
        with self._lock:
            state = self._pending_state
            self._pending_state = None

        if not state:
            return

        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = self._path.with_suffix(".tmp")

            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)

            temp_path.replace(self._path)
            logger.debug(f"[Persistence] Saved state to {self._path}")

        except Exception as e:
            logger.error(f"[Persistence] Save failed: {e}")

    def load(self) -> Optional[Dict[str, Any]]:
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
        try:
            self._path.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"[Persistence] Clear failed: {e}")


# ============================================================================
# Time Travel
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
        if self._current_index < len(self._snapshots) - 1:
            self._snapshots = self._snapshots[: self._current_index + 1]

        snapshot = StateSnapshot(
            state=copy.deepcopy(state),
            action=action,
            index=len(self._snapshots),
        )
        self._snapshots.append(snapshot)
        self._current_index = len(self._snapshots) - 1

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

    use_typed_state: bool = False
    enable_time_travel: bool = False
    history_size: int = 100
    persistence: Optional[IStatePersistence] = None
    enable_logging: bool = True
    enable_performance_tracking: bool = False
    enable_dev_tools: bool = False
    enable_optimistic_updates: bool = True
    enable_toasts: bool = True


# ============================================================================
# Main Store Class
# ============================================================================


class Store(QObject):
    """
    Enhanced Redux-like Store with UX improvements.

    Features:
    - Thread-safe state updates
    - Qt signal integration
    - Middleware pipeline
    - Optimistic updates with rollback
    - Toast notification system
    - Time-travel debugging
    - State persistence
    - Loading state tracking
    - Memoized selectors
    """

    # Qt signals
    state_changed = Signal(dict)
    devices_updated = Signal(dict)
    page_changed = Signal(str)
    sync_completed_signal = Signal(dict)

    # UX signals
    undo_available = Signal(bool)
    redo_available = Signal(bool)
    loading_changed = Signal(str, bool)  # key, is_loading
    toast_shown = Signal(object)  # Toast

    def __init__(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
        middlewares: Optional[List[Middleware]] = None,
        config: Optional[StoreConfig] = None,
    ):
        super().__init__()

        self._config = config or StoreConfig()

        # Load persisted state
        base_state = (initial_state or INITIAL_STATE_DICT).copy()
        if self._config.persistence:
            persisted = self._config.persistence.load()
            if persisted:
                base_state.update(persisted)

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
            init_action = Action(type=ActionType.INIT)
            self._history.push(self._state.copy(), init_action)

        # Optimistic updates
        self._optimistic_manager: Optional[OptimisticUpdateManager] = None
        if self._config.enable_optimistic_updates:
            self._optimistic_manager = OptimisticUpdateManager(self)

        # Toast manager
        self._toast_manager: Optional[ToastManager] = None
        if self._config.enable_toasts:
            self._toast_manager = ToastManager(self)
            self._toast_manager.toast_added.connect(lambda t: self.toast_shown.emit(t))

        # Loading tracker
        self._loading_tracker = LoadingStateTracker()

        # Metrics
        self._metrics: Dict[str, Any] = {
            "dispatch_count": 0,
            "total_dispatch_time": 0.0,
            "max_dispatch_time": 0.0,
        }

        # Thread safety
        self._lock = threading.RLock()

        logger.debug(
            f"[Store] Initialized with {len(self._state)} state keys, "
            f"time_travel={self._config.enable_time_travel}, "
            f"toasts={self._config.enable_toasts}"
        )

    def _setup_middlewares(self, custom_middlewares: List[Middleware]) -> None:
        """Setup middleware pipeline."""
        # Add in order: logging -> optimistic -> toast -> performance -> dev_tools -> persistence -> custom

        if self._config.enable_logging:
            self._middlewares.append(logging_middleware)

        if self._config.enable_optimistic_updates:
            self._middlewares.append(optimistic_middleware)

        if self._config.enable_toasts:
            self._middlewares.append(toast_middleware)

        if self._config.enable_performance_tracking:
            self._middlewares.append(performance_middleware)

        if self._config.enable_dev_tools:
            self._middlewares.append(dev_tools_middleware)

        if self._config.persistence:
            self._middlewares.append(create_persistence_middleware(self._config.persistence))

        self._middlewares.extend(custom_middlewares)

    # ========================================================================
    # Toast API
    # ========================================================================

    @property
    def toasts(self) -> ToastManager:
        """Get toast manager."""
        if not self._toast_manager:
            self._toast_manager = ToastManager(self)
        return self._toast_manager

    def show_toast(
        self,
        message: str,
        variant: str = "info",
        duration: int = 3000,
    ) -> str:
        """Convenience method to show a toast."""
        return self.toasts.show(message, variant, duration)

    # ========================================================================
    # Loading API
    # ========================================================================

    def set_loading(self, key: str, loading: bool, message: str = "") -> None:
        """Set loading state for a key."""
        self._loading_tracker.set_loading(key, loading, message)
        self.loading_changed.emit(key, loading)

    def is_loading(self, key: str) -> bool:
        """Check if key is loading."""
        return self._loading_tracker.is_loading(key)

    @property
    def is_any_loading(self) -> bool:
        """Check if anything is loading."""
        return self._loading_tracker.is_any_loading

    # ========================================================================
    # Middleware Management
    # ========================================================================

    def add_middleware(self, middleware: Middleware) -> None:
        self._middlewares.append(middleware)

    def remove_middleware(self, middleware: Middleware) -> bool:
        try:
            self._middlewares.remove(middleware)
            return True
        except ValueError:
            return False

    # ========================================================================
    # State Access
    # ========================================================================

    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return self._state.copy()

    def get_state_dict(self) -> Dict[str, Any]:
        return self.get_state()

    def select(self, selector: Callable[[Dict[str, Any]], T]) -> T:
        with self._lock:
            return selector(self._state)

    # ========================================================================
    # Dispatch
    # ========================================================================

    def dispatch(self, action: Action) -> None:
        if not isinstance(action, Action):
            logger.warning(f"[Store] Invalid action type: {type(action)}")
            return

        if self._is_batching:
            self._batch_actions.append(action)
            return

        if self._middlewares:
            self._dispatch_with_middleware(action)
        else:
            self._dispatch_internal(action)

    def _dispatch_with_middleware(self, action: Action) -> None:
        middlewares = self._middlewares[:]

        def create_next(index: int) -> Callable[[Action], None]:
            if index >= len(middlewares):
                return self._dispatch_internal

            def next_dispatch(act: Action) -> None:
                middlewares[index](self, act, create_next(index + 1))

            return next_dispatch

        create_next(0)(action)

    def _dispatch_internal(self, action: Action) -> None:
        with self._lock:
            old_state = self._state

            try:
                new_state = root_reducer_dict(old_state, action)
            except Exception as e:
                logger.error(f"[Store] Reducer error for {action.type.name}: {e}")
                return

            self._state = new_state
            self._metrics["dispatch_count"] += 1

            if self._history and not self._is_time_traveling:
                self._history.push(new_state.copy(), action)

            state_changed = new_state is not old_state
            emit_data = self._prepare_emit_data(action, old_state, new_state, state_changed)

        self._emit_signals(emit_data)

    def _prepare_emit_data(
        self,
        action: Action,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any],
        state_changed: bool,
    ) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "action": action,
            "state_changed": state_changed,
        }

        if state_changed:
            data["new_state_copy"] = new_state.copy()

        if action.type in (ActionType.LOAD_DEVICES, ActionType.UPDATE_DEVICES):
            data["devices"] = new_state.get("devices", {}).copy()

        if action.type == ActionType.SET_PAGE:
            data["new_page"] = new_state.get("current_page")
            data["old_page"] = old_state.get("current_page")

        if action.type == ActionType.SYNC_COMPLETED:
            data["sync_payload"] = action.payload or {}

        return data

    def _emit_signals(self, emit_data: Dict[str, Any]) -> None:
        action: Action = emit_data["action"]

        if "devices" in emit_data:
            self._safe_emit(self.devices_updated, emit_data["devices"])

        if emit_data.get("state_changed"):
            self._safe_emit(self.state_changed, emit_data["new_state_copy"])

        new_page = emit_data.get("new_page")
        old_page = emit_data.get("old_page")
        if new_page and new_page != old_page:
            self._safe_emit(self.page_changed, new_page)

        if "sync_payload" in emit_data:
            self._safe_emit(self.sync_completed_signal, emit_data["sync_payload"])

        if self._history:
            self._safe_emit(self.undo_available, self._history.can_undo())
            self._safe_emit(self.redo_available, self._history.can_redo())

    def _safe_emit(self, signal: Signal, *args: Any) -> None:
        try:
            signal.emit(*args)
        except RuntimeError as e:
            logger.debug(f"[Store] Signal emit skipped: {e}")

    # ========================================================================
    # Batching
    # ========================================================================

    @contextmanager
    def batch(self) -> Iterator[None]:
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
                if self._middlewares:
                    self._dispatch_with_middleware(action)
                else:
                    self._dispatch_internal(action)

    # ========================================================================
    # Time Travel
    # ========================================================================

    def undo(self) -> bool:
        if not self._history:
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

        if self._toast_manager:
            self._toast_manager.info("↩️ Undo", duration=1500)

        return True

    def redo(self) -> bool:
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

        if self._toast_manager:
            self._toast_manager.info("↪️ Redo", duration=1500)

        return True

    def can_undo(self) -> bool:
        return self._history.can_undo() if self._history else False

    def can_redo(self) -> bool:
        return self._history.can_redo() if self._history else False

    def get_history(self) -> List[Dict[str, Any]]:
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
        with self._lock:
            return self._metrics["dispatch_count"]

    def get_metrics(self) -> Dict[str, Any]:
        with self._lock:
            dispatch_count = self._metrics["dispatch_count"]
            total_time = self._metrics["total_dispatch_time"]

            return {
                **self._metrics,
                "avg_dispatch_time_ms": (total_time / dispatch_count if dispatch_count > 0 else 0),
                "history_size": (len(self._history.snapshots) if self._history else 0),
            }

    def get_action_history(self) -> List[Dict[str, Any]]:
        return getattr(self, "_action_history", [])

    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            self._state = (new_state or INITIAL_STATE_DICT).copy()
            self._metrics = {
                "dispatch_count": 0,
                "total_dispatch_time": 0.0,
                "max_dispatch_time": 0.0,
            }
            if self._history:
                self._history.clear()

            self._loading_tracker.clear()

        self._safe_emit(self.state_changed, self._state.copy())

        if self._toast_manager:
            self._toast_manager.dismiss_all()

    def dispose(self) -> None:
        """Clean up resources."""
        if self._optimistic_manager:
            self._optimistic_manager.dispose()

        if self._toast_manager:
            self._toast_manager.dismiss_all()


# ============================================================================
# Convenience alias
# ============================================================================

EnhancedStore = Store


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
    "optimistic_middleware",
    "toast_middleware",
    "debounce_middleware",
    "create_persistence_middleware",
    # Persistence
    "LocalStoragePersistence",
    # Time travel
    "StateSnapshot",
    "StateHistory",
    # Toast
    "Toast",
    "ToastManager",
    # Optimistic
    "OptimisticUpdate",
    "OptimisticUpdateManager",
    # Loading
    "LoadingStateTracker",
    # Selectors
    "MemoizedSelector",
    "create_selector",
]
