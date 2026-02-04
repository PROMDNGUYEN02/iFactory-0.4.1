# src/iFactory/presentation/viewmodels/base.py
"""
Enhanced Base ViewModel with reactive properties and advanced features.

Features:
- Reactive computed properties
- Automatic UI updates
- Dispose pattern for cleanup
- Command pattern with CanExecute
- Property change tracking
- Weak event pattern
- Validation support
"""

from __future__ import annotations

import asyncio
import logging
import weakref
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum, auto
from functools import cached_property, wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Protocol,
    Set,
    TypeVar,
    Union,
    runtime_checkable,
)

from PySide6.QtCore import QObject, Signal, Slot

logger = logging.getLogger(__name__)

T = TypeVar("T")
TResult = TypeVar("TResult")


# ============================================================================
# UI State
# ============================================================================


class UiStateType(StrEnum):
    """UI state types."""

    IDLE = auto()
    LOADING = auto()
    SUCCESS = auto()
    ERROR = auto()
    EMPTY = auto()


@dataclass(frozen=True)
class UiState(Generic[T]):
    """
    Immutable UI state container.

    Represents the current state of a UI component:
    - Idle: Initial/waiting state
    - Loading: Operation in progress
    - Success: Operation completed with data
    - Error: Operation failed with message
    - Empty: No data available
    """

    type: UiStateType
    data: Optional[T] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def idle(cls) -> "UiState[T]":
        return cls(type=UiStateType.IDLE)

    @classmethod
    def loading(cls, message: str = "Loading...") -> "UiState[T]":
        return cls(type=UiStateType.LOADING, message=message)

    @classmethod
    def success(cls, data: T = None, message: str = "") -> "UiState[T]":
        return cls(type=UiStateType.SUCCESS, data=data, message=message)

    @classmethod
    def error(cls, message: str, code: Optional[str] = None) -> "UiState[T]":
        return cls(
            type=UiStateType.ERROR,
            message=message,
            metadata={"code": code} if code else None,
        )

    @classmethod
    def empty(cls, message: str = "No data") -> "UiState[T]":
        return cls(type=UiStateType.EMPTY, message=message)

    @property
    def is_idle(self) -> bool:
        return self.type == UiStateType.IDLE

    @property
    def is_loading(self) -> bool:
        return self.type == UiStateType.LOADING

    @property
    def is_success(self) -> bool:
        return self.type == UiStateType.SUCCESS

    @property
    def is_error(self) -> bool:
        return self.type == UiStateType.ERROR

    @property
    def is_empty(self) -> bool:
        return self.type == UiStateType.EMPTY

    @property
    def error_code(self) -> Optional[str]:
        if self.metadata:
            return self.metadata.get("code")
        return None

    def map(self, func: Callable[[T], TResult]) -> "UiState[TResult]":
        """Transform success data."""
        if self.is_success and self.data is not None:
            return UiState.success(func(self.data), self.message)
        return UiState(type=self.type, message=self.message, metadata=self.metadata)

    def flat_map(self, func: Callable[[T], "UiState[TResult]"]) -> "UiState[TResult]":
        """Chain state transformations."""
        if self.is_success and self.data is not None:
            return func(self.data)
        return UiState(type=self.type, message=self.message, metadata=self.metadata)

    def get_or_default(self, default: T) -> T:
        """Get data or return default."""
        return self.data if self.data is not None else default

    def on_success(self, handler: Callable[[T], None]) -> "UiState[T]":
        """Execute handler if success."""
        if self.is_success and self.data is not None:
            handler(self.data)
        return self

    def on_error(self, handler: Callable[[str], None]) -> "UiState[T]":
        """Execute handler if error."""
        if self.is_error:
            handler(self.message)
        return self


# ============================================================================
# Validation
# ============================================================================


@dataclass(frozen=True)
class ValidationResult:
    """Result of validation."""

    is_valid: bool
    errors: tuple[str, ...] = ()

    @classmethod
    def valid(cls) -> "ValidationResult":
        return cls(is_valid=True)

    @classmethod
    def invalid(cls, *errors: str) -> "ValidationResult":
        return cls(is_valid=False, errors=errors)

    def combine(self, other: "ValidationResult") -> "ValidationResult":
        """Combine two validation results."""
        if self.is_valid and other.is_valid:
            return ValidationResult.valid()
        return ValidationResult.invalid(*(self.errors + other.errors))


@runtime_checkable
class IValidatable(Protocol):
    """Protocol for validatable objects."""

    def validate(self) -> ValidationResult:
        """Validate the object."""
        ...


# ============================================================================
# Reactive Property
# ============================================================================


class ReactiveProperty(Generic[T]):
    """
    Reactive property that notifies on change.

    Features:
    - Change notification
    - Validation
    - Weak references for subscribers
    - Coercion support

    Usage:
        class MyViewModel(BaseViewModel):
            def __init__(self):
                super().__init__()
                self._count = ReactiveProperty(
                    initial_value=0,
                    on_change=self._on_count_changed,
                    validator=lambda x: x >= 0,
                )

            @property
            def count(self) -> int:
                return self._count.value

            @count.setter
            def count(self, value: int) -> None:
                self._count.value = value
    """

    def __init__(
        self,
        initial_value: T,
        on_change: Optional[Callable[[T, T], None]] = None,
        validator: Optional[Callable[[T], bool]] = None,
        coercer: Optional[Callable[[Any], T]] = None,
        name: str = "",
    ):
        self._value = initial_value
        self._on_change = on_change
        self._validator = validator
        self._coercer = coercer
        self._name = name
        self._subscribers: List[weakref.ref] = []
        self._is_updating = False

    @property
    def value(self) -> T:
        return self._value

    @value.setter
    def value(self, new_value: T) -> None:
        # Prevent recursive updates
        if self._is_updating:
            return

        # Coerce value if coercer provided
        if self._coercer:
            try:
                new_value = self._coercer(new_value)
            except Exception as e:
                logger.warning(f"Coercion failed for {self._name}: {e}")
                return

        # Skip if same value
        if self._value == new_value:
            return

        # Validate if validator provided
        if self._validator and not self._validator(new_value):
            logger.warning(f"Validation failed for {self._name}: {new_value}")
            return

        self._is_updating = True
        try:
            old_value = self._value
            self._value = new_value

            if self._on_change:
                self._on_change(old_value, new_value)

            self._notify_subscribers(old_value, new_value)
        finally:
            self._is_updating = False

    def subscribe(
        self,
        callback: Callable[[T, T], None],
    ) -> Callable[[], None]:
        """Subscribe to changes. Returns unsubscribe function."""
        ref = weakref.ref(callback)
        self._subscribers.append(ref)

        def unsubscribe():
            try:
                self._subscribers.remove(ref)
            except ValueError:
                pass

        return unsubscribe

    def _notify_subscribers(self, old: T, new: T) -> None:
        """Notify all subscribers of change."""
        dead_refs = []

        for ref in self._subscribers:
            callback = ref()
            if callback is None:
                dead_refs.append(ref)
            else:
                try:
                    callback(old, new)
                except Exception as e:
                    logger.error(f"Subscriber error: {e}")

        # Clean up dead references
        for ref in dead_refs:
            self._subscribers.remove(ref)

    def force_notify(self) -> None:
        """Force notify all subscribers with current value."""
        self._notify_subscribers(self._value, self._value)
        if self._on_change:
            self._on_change(self._value, self._value)


class ComputedProperty(Generic[T]):
    """
    Computed property that derives from other properties.

    Automatically updates when dependencies change.

    Usage:
        self._first_name = ReactiveProperty("John")
        self._last_name = ReactiveProperty("Doe")
        self._full_name = ComputedProperty(
            compute=lambda: f"{self._first_name.value} {self._last_name.value}",
            dependencies=[self._first_name, self._last_name],
        )
    """

    def __init__(
        self,
        compute: Callable[[], T],
        dependencies: List[ReactiveProperty],
        on_change: Optional[Callable[[T, T], None]] = None,
    ):
        self._compute = compute
        self._on_change = on_change
        self._cached_value: Optional[T] = None
        self._is_dirty = True

        # Subscribe to dependencies
        for dep in dependencies:
            dep.subscribe(self._on_dependency_changed)

    def _on_dependency_changed(self, old: Any, new: Any) -> None:
        """Mark as dirty when dependency changes."""
        self._is_dirty = True

    @property
    def value(self) -> T:
        """Get computed value (cached if not dirty)."""
        if self._is_dirty:
            old_value = self._cached_value
            self._cached_value = self._compute()
            self._is_dirty = False

            if self._on_change and old_value != self._cached_value:
                self._on_change(old_value, self._cached_value)

        return self._cached_value


# ============================================================================
# Command Pattern
# ============================================================================


class ICommand(ABC):
    """Command interface with CanExecute support."""

    @abstractmethod
    def execute(self, parameter: Any = None) -> None:
        """Execute the command."""
        pass

    @abstractmethod
    def can_execute(self, parameter: Any = None) -> bool:
        """Check if command can be executed."""
        pass

    @property
    @abstractmethod
    def is_executing(self) -> bool:
        """Check if command is currently executing."""
        pass


class RelayCommand(ICommand):
    """
    Simple command implementation.

    Usage:
        self.save_command = RelayCommand(
            execute=self._save,
            can_execute=lambda: self.is_valid and not self.is_saving,
        )
    """

    def __init__(
        self,
        execute: Callable[[Any], None],
        can_execute: Optional[Callable[[Any], bool]] = None,
        on_can_execute_changed: Optional[Callable[[], None]] = None,
    ):
        self._execute = execute
        self._can_execute = can_execute or (lambda _: True)
        self._on_can_execute_changed = on_can_execute_changed
        self._is_executing = False

    def execute(self, parameter: Any = None) -> None:
        if not self.can_execute(parameter):
            return

        self._is_executing = True
        try:
            self._execute(parameter)
        finally:
            self._is_executing = False

    def can_execute(self, parameter: Any = None) -> bool:
        if self._is_executing:
            return False
        return self._can_execute(parameter)

    @property
    def is_executing(self) -> bool:
        return self._is_executing

    def raise_can_execute_changed(self) -> None:
        """Notify that can_execute may have changed."""
        if self._on_can_execute_changed:
            self._on_can_execute_changed()


class AsyncRelayCommand(ICommand):
    """
    Async command implementation with cancellation support.

    Usage:
        self.load_command = AsyncRelayCommand(
            execute=self._load_data,
            can_execute=lambda: not self.is_loading,
            on_complete=self._on_load_complete,
        )
    """

    def __init__(
        self,
        execute: Callable[[Any], Awaitable[None]],
        can_execute: Optional[Callable[[Any], bool]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        self._execute = execute
        self._can_execute = can_execute or (lambda _: True)
        self._on_error = on_error
        self._on_complete = on_complete
        self._is_executing = False
        self._current_task: Optional[asyncio.Task] = None

    def execute(self, parameter: Any = None) -> None:
        """Start async execution."""
        if not self.can_execute(parameter):
            return

        self._is_executing = True

        async def run():
            try:
                await self._execute(parameter)
            except asyncio.CancelledError:
                logger.debug("Command cancelled")
            except Exception as e:
                if self._on_error:
                    self._on_error(e)
                else:
                    logger.error(f"Command error: {e}")
            finally:
                self._is_executing = False
                self._current_task = None
                if self._on_complete:
                    self._on_complete()

        self._current_task = asyncio.create_task(run())

    def can_execute(self, parameter: Any = None) -> bool:
        if self._is_executing:
            return False
        return self._can_execute(parameter)

    @property
    def is_executing(self) -> bool:
        return self._is_executing

    def cancel(self) -> None:
        """Cancel current execution."""
        if self._current_task and not self._current_task.done():
            self._current_task.cancel()
            self._is_executing = False


# ============================================================================
# Property Change Tracking
# ============================================================================


class PropertyChangeTracker:
    """
    Tracks property changes for dirty checking.

    Usage:
        tracker = PropertyChangeTracker()
        tracker.set("name", "John")
        tracker.set("name", "Jane")

        print(tracker.is_dirty)  # True
        print(tracker.changed_properties)  # {"name"}

        tracker.accept_changes()
        print(tracker.is_dirty)  # False
    """

    def __init__(self):
        self._original: Dict[str, Any] = {}
        self._current: Dict[str, Any] = {}

    def set(self, name: str, value: Any) -> None:
        """Set a property value."""
        if name not in self._original:
            self._original[name] = value
        self._current[name] = value

    @property
    def is_dirty(self) -> bool:
        """Check if any property has changed."""
        return self._original != self._current

    @property
    def changed_properties(self) -> Set[str]:
        """Get names of changed properties."""
        changed = set()
        for name in self._current:
            if name in self._original:
                if self._original[name] != self._current[name]:
                    changed.add(name)
            else:
                changed.add(name)
        return changed

    def accept_changes(self) -> None:
        """Accept all changes (resets dirty state)."""
        self._original = self._current.copy()

    def reject_changes(self) -> None:
        """Reject all changes (revert to original)."""
        self._current = self._original.copy()

    def get_original(self, name: str) -> Any:
        """Get original value of property."""
        return self._original.get(name)

    def get_current(self, name: str) -> Any:
        """Get current value of property."""
        return self._current.get(name)

    def clear(self) -> None:
        """Clear all tracked properties."""
        self._original.clear()
        self._current.clear()


# ============================================================================
# Base ViewModel
# ============================================================================


class BaseViewModel(QObject):
    """
    Enhanced base class for all ViewModels.

    Features:
    - UI state management
    - Reactive properties
    - Command support
    - Dispose pattern
    - Property change tracking
    - Validation

    Lifecycle:
    1. __init__() - Create instance
    2. initialize() - Setup state and bindings
    3. ... normal operation ...
    4. dispose() - Cleanup resources
    """

    # Signals
    stateChanged = Signal(object)  # UiState
    errorOccurred = Signal(str)
    propertyChanged = Signal(str, object)  # property_name, new_value
    disposed = Signal()

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._ui_state: UiState = UiState.idle()
        self._is_disposed = False
        self._is_initialized = False
        self._disposables: List[Callable[[], None]] = []
        self._property_tracker = PropertyChangeTracker()
        self._validation_errors: Dict[str, str] = {}

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def initialize(self) -> None:
        """
        Initialize the ViewModel.

        Override in subclasses to setup state and bindings.
        Call super().initialize() at the start.
        """
        if self._is_initialized:
            return
        self._is_initialized = True
        logger.debug(f"[{self.__class__.__name__}] Initialized")

    def add_disposable(self, dispose_func: Callable[[], None]) -> None:
        """Add a cleanup function to be called on dispose."""
        self._disposables.append(dispose_func)

    def dispose(self) -> None:
        """Clean up resources."""
        if self._is_disposed:
            return

        self._is_disposed = True

        # Run all dispose functions
        for dispose_func in self._disposables:
            try:
                dispose_func()
            except Exception as e:
                logger.error(f"Dispose error: {e}")

        self._disposables.clear()
        self._property_tracker.clear()
        self._validation_errors.clear()

        self.disposed.emit()
        logger.debug(f"[{self.__class__.__name__}] Disposed")

    @property
    def is_disposed(self) -> bool:
        return self._is_disposed

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    # ========================================================================
    # UI State
    # ========================================================================

    @property
    def state(self) -> UiState:
        """Current UI state."""
        return self._ui_state

    @property
    def is_loading(self) -> bool:
        return self._ui_state.is_loading

    @property
    def is_error(self) -> bool:
        return self._ui_state.is_error

    @property
    def error_message(self) -> str:
        return self._ui_state.message if self._ui_state.is_error else ""

    def _set_state(self, state: UiState) -> None:
        """Update UI state."""
        if self._is_disposed:
            return

        self._ui_state = state
        self.stateChanged.emit(state)

        if state.is_error:
            self.errorOccurred.emit(state.message)

    def _set_loading(self, loading: bool, message: str = "Loading...") -> None:
        """Set loading state."""
        if loading:
            self._set_state(UiState.loading(message))
        else:
            self._set_state(UiState.idle())

    def _set_error(self, message: str, code: Optional[str] = None) -> None:
        """Set error state."""
        self._set_state(UiState.error(message, code))
        logger.error(f"[{self.__class__.__name__}] {message}")

    def _set_success(self, data: Any = None, message: str = "") -> None:
        """Set success state."""
        self._set_state(UiState.success(data, message))

    def _set_empty(self, message: str = "No data") -> None:
        """Set empty state."""
        self._set_state(UiState.empty(message))

    # ========================================================================
    # Property Tracking
    # ========================================================================

    def track_property(self, name: str, value: Any) -> None:
        """Track a property for dirty checking."""
        self._property_tracker.set(name, value)

    @property
    def is_dirty(self) -> bool:
        """Check if any tracked property has changed."""
        return self._property_tracker.is_dirty

    def accept_changes(self) -> None:
        """Accept all property changes."""
        self._property_tracker.accept_changes()

    def reject_changes(self) -> None:
        """Reject all property changes."""
        self._property_tracker.reject_changes()

    def notify_property_changed(self, name: str, value: Any) -> None:
        """Notify that a property has changed."""
        self.propertyChanged.emit(name, value)

    # ========================================================================
    # Validation
    # ========================================================================

    def set_validation_error(self, property_name: str, error: str) -> None:
        """Set validation error for a property."""
        self._validation_errors[property_name] = error

    def clear_validation_error(self, property_name: str) -> None:
        """Clear validation error for a property."""
        self._validation_errors.pop(property_name, None)

    def clear_all_validation_errors(self) -> None:
        """Clear all validation errors."""
        self._validation_errors.clear()

    def get_validation_error(self, property_name: str) -> Optional[str]:
        """Get validation error for a property."""
        return self._validation_errors.get(property_name)

    @property
    def has_validation_errors(self) -> bool:
        """Check if there are any validation errors."""
        return bool(self._validation_errors)

    @property
    def validation_errors(self) -> Dict[str, str]:
        """Get all validation errors."""
        return self._validation_errors.copy()


# ============================================================================
# Async ViewModel Mixin
# ============================================================================


class AsyncViewModelMixin:
    """
    Mixin for async operation support.

    Provides helper methods for running async operations
    with proper error handling and cancellation.
    """

    def __init__(self):
        self._pending_tasks: List[asyncio.Task] = []

    async def run_async(
        self,
        coro: Awaitable[T],
        on_success: Optional[Callable[[T], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        set_loading: bool = True,
        loading_message: str = "Loading...",
    ) -> Optional[T]:
        """
        Run an async operation with proper handling.

        Args:
            coro: Coroutine to run
            on_success: Callback on success
            on_error: Callback on error
            set_loading: Whether to set loading state
            loading_message: Message to show while loading

        Returns:
            Result on success, None on error
        """
        if hasattr(self, "_is_disposed") and self._is_disposed:
            return None

        if set_loading and hasattr(self, "_set_loading"):
            self._set_loading(True, loading_message)

        try:
            result = await coro

            if on_success:
                on_success(result)

            return result

        except asyncio.CancelledError:
            logger.debug("Async operation cancelled")
            return None

        except Exception as e:
            logger.error(f"Async operation failed: {e}")

            if on_error:
                on_error(e)
            elif hasattr(self, "_set_error"):
                self._set_error(str(e))

            return None

        finally:
            if set_loading and hasattr(self, "_set_loading"):
                self._set_loading(False)

    def cancel_pending_tasks(self) -> None:
        """Cancel all pending async tasks."""
        for task in self._pending_tasks:
            if not task.done():
                task.cancel()
        self._pending_tasks.clear()


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # State
    "UiState",
    "UiStateType",
    # Validation
    "ValidationResult",
    "IValidatable",
    # Reactive
    "ReactiveProperty",
    "ComputedProperty",
    # Commands
    "ICommand",
    "RelayCommand",
    "AsyncRelayCommand",
    # Tracking
    "PropertyChangeTracker",
    # Base
    "BaseViewModel",
    "AsyncViewModelMixin",
]
