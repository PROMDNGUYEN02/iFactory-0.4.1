"""
Redux-like State Management for Presentation Layer.

Architecture:
- Store: Centralized state container
- Actions: State change requests
- Reducers: Pure functions that update state
- Selectors: Computed state queries
- Middleware: Side effects handling (async operations, logging)
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    TypeVar,
    Protocol,
    runtime_checkable,
)
from datetime import datetime

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ActionType(Enum):
    """Standard action types."""
    INITIALIZE = "INITIALIZE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
    RESET = "RESET"
    LOADING_START = "LOADING_START"
    LOADING_END = "LOADING_END"
    ERROR = "ERROR"


@dataclass
class Action:
    """
    Immutable action descriptor.
    
    Actions describe state changes but don't implement them.
    """
    type: str
    payload: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def with_payload(self, payload: Any) -> 'Action':
        """Create new action with different payload."""
        return Action(
            type=self.type,
            payload=payload,
            metadata=self.metadata,
            timestamp=self.timestamp
        )


@dataclass
class StateSnapshot:
    """
    Immutable state snapshot for debugging and time-travel.
    """
    state: Dict[str, Any]
    action: Action
    timestamp: datetime = field(default_factory=datetime.now)


@runtime_checkable
class Reducer(Protocol[T]):
    """
    Protocol for state reducers.
    
    Reducers are pure functions that transform state based on actions.
    """
    def __call__(self, state: T, action: Action) -> T:
        """
        Transform state based on action.
        
        Args:
            state: Current state
            action: Action to apply
            
        Returns:
            New state (immutable)
        """
        ...


class Middleware(ABC):
    """
    Base class for middleware.
    
    Middleware can intercept actions, modify them, or perform side effects.
    """
    
    @abstractmethod
    def process(
        self,
        store: 'Store',
        action: Action,
        next_handler: Callable[[Action], None]
    ) -> None:
        """
        Process action and call next handler.
        
        Args:
            store: Store instance
            action: Action being dispatched
            next_handler: Next middleware in chain
        """
        pass


class LoggingMiddleware(Middleware):
    """Logs all actions and state changes."""
    
    def process(
        self,
        store: 'Store',
        action: Action,
        next_handler: Callable[[Action], None]
    ) -> None:
        logger.debug(f"[Middleware] Action: {action.type}")
        start_state = store.get_state()
        next_handler(action)
        end_state = store.get_state()
        logger.debug(f"[Middleware] State changed: {start_state} -> {end_state}")


class ErrorHandlingMiddleware(Middleware):
    """Handles errors in action processing."""
    
    def process(
        self,
        store: 'Store',
        action: Action,
        next_handler: Callable[[Action], None]
    ) -> None:
        try:
            next_handler(action)
        except Exception as e:
            logger.error(f"[Middleware] Error processing action {action.type}: {e}")
            error_action = Action(
                type=ActionType.ERROR.value,
                payload=str(e),
                metadata={"original_action": action.type}
            )
            next_handler(error_action)


class Store(QObject):
    """
    Centralized state container following Redux pattern.
    
    Features:
    - Single source of truth
    - Predictable state updates through reducers
    - Middleware support for side effects
    - State change notifications via signals
    - Time-travel debugging support
    """
    
    state_changed = Signal(dict)
    error_occurred = Signal(str)
    
    def __init__(
        self,
        initial_state: Dict[str, Any],
        reducers: Dict[str, Reducer],
        parent: Optional[QObject] = None
    ) -> None:
        super().__init__(parent)
        self._state: Dict[str, Any] = initial_state.copy()
        self._reducers = reducers.copy()
        self._middleware: List[Middleware] = []
        self._snapshots: List[StateSnapshot] = []
        self._is_dispatching = False
        self._max_snapshots = 100
        
        logger.debug("[Store] Created with initial state")
    
    def add_middleware(self, middleware: Middleware) -> None:
        """Add middleware to processing chain."""
        self._middleware.append(middleware)
        logger.debug(f"[Store] Middleware added: {middleware.__class__.__name__}")
    
    def dispatch(self, action: Action) -> None:
        """
        Dispatch action to update state.
        
        Args:
            action: Action to dispatch
        """
        if self._is_dispatching:
            raise RuntimeError("Cannot dispatch actions during dispatch")
        
        logger.debug(f"[Store] Dispatching action: {action.type}")
        
        self._is_dispatching = True
        try:
            self._process_action(action)
            self._emit_state_changed()
        finally:
            self._is_dispatching = False
    
    def _process_action(self, action: Action) -> None:
        """Process action through middleware chain and reducers."""
        if not self._middleware:
            self._apply_reducers(action)
        else:
            self._process_with_middleware(action, 0)
    
    def _process_with_middleware(self, action: Action, index: int) -> None:
        """Process action through middleware chain."""
        if index >= len(self._middleware):
            self._apply_reducers(action)
            return
        
        def next_handler(act: Action) -> None:
            self._process_with_middleware(act, index + 1)
        
        self._middleware[index].process(self, action, next_handler)
    
    def _apply_reducers(self, action: Action) -> None:
        """Apply action to relevant reducers."""
        old_state = self._state.copy()
        
        for key, reducer in self._reducers.items():
            if key in self._state:
                self._state[key] = reducer(self._state[key], action)
        
        new_state = self._state.copy()
        
        if old_state != new_state:
            self._save_snapshot(action, old_state, new_state)
            logger.debug(f"[Store] State updated by action: {action.type}")
    
    def _save_snapshot(
        self,
        action: Action,
        old_state: Dict[str, Any],
        new_state: Dict[str, Any]
    ) -> None:
        """Save state snapshot for time-travel debugging."""
        snapshot = StateSnapshot(
            state=new_state.copy(),
            action=action
        )
        
        self._snapshots.append(snapshot)
        
        if len(self._snapshots) > self._max_snapshots:
            self._snapshots.pop(0)
    
    def get_state(self) -> Dict[str, Any]:
        """Get current state (immutable copy)."""
        return self._state.copy()
    
    def get_state_slice(self, slice_name: str) -> Any:
        """Get specific slice of state."""
        return self._state.get(slice_name)
    
    def get_snapshots(self) -> List[StateSnapshot]:
        """Get state history for debugging."""
        return self._snapshots.copy()
    
    def time_travel(self, snapshot_index: int) -> None:
        """
        Restore state from snapshot (time-travel debugging).
        
        Args:
            snapshot_index: Index of snapshot to restore
        """
        if 0 <= snapshot_index < len(self._snapshots):
            snapshot = self._snapshots[snapshot_index]
            self._state = snapshot.state.copy()
            self._emit_state_changed()
            logger.debug(f"[Store] Time-traveled to snapshot {snapshot_index}")
    
    def _emit_state_changed(self) -> None:
        """Emit state change signal."""
        self.state_changed.emit(self.get_state())
    
    def reset(self, new_state: Optional[Dict[str, Any]] = None) -> None:
        """
        Reset store to initial or custom state.
        
        Args:
            new_state: Optional new state (uses initial if None)
        """
        if new_state:
            self._state = new_state.copy()
        else:
            self._state = {k: v for k, v in self._state.items()}
        
        self._snapshots.clear()
        self._emit_state_changed()
        logger.debug("[Store] State reset")


class Selector:
    """
    Computed state queries.
    
    Selectors provide efficient ways to query and transform state.
    """
    
    @staticmethod
    def create_selector(
        slice_name: str,
        transform_func: Optional[Callable[[Any], Any]] = None
    ) -> Callable[[Store], Any]:
        """
        Create a selector for a state slice.
        
        Args:
            slice_name: Name of state slice
            transform_func: Optional transformation function
            
        Returns:
            Selector function
        """
        def selector(store: Store) -> Any:
            data = store.get_state_slice(slice_name)
            if transform_func:
                return transform_func(data)
            return data
        return selector
    
    @staticmethod
    def create_memoized_selector(
        *selectors: Callable[[Store], Any],
        combiner: Optional[Callable[..., Any]] = None
    ) -> Callable[[Store], Any]:
        """
        Create a memoized selector that combines other selectors.
        
        Args:
            selectors: Input selectors
            combiner: Function to combine selector results
            
        Returns:
            Combined selector
        """
        _cache = {}
        
        def combined_selector(store: Store) -> Any:
            key = tuple(s(store) for s in selectors)
            if key not in _cache:
                if combiner:
                    _cache[key] = combiner(*key)
                else:
                    _cache[key] = key[0] if len(key) == 1 else list(key)
            return _cache[key]
        
        return combined_selector


__all__ = [
    'ActionType',
    'Action',
    'StateSnapshot',
    'Reducer',
    'Middleware',
    'LoggingMiddleware',
    'ErrorHandlingMiddleware',
    'Store',
    'Selector',
]
