"""
Base ViewModel with Reactive Signals and UiState Pattern.

This module provides the foundation for all ViewModels in the MVVM architecture.
ViewModels are the sole owners of UI state and expose reactive signals for Views to bind to.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Callable, Generic, List, Optional, TypeVar

from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


# =============================================================================
# UI State Pattern
# =============================================================================


class UiStateType(Enum):
    """Enumeration of possible UI states."""

    IDLE = auto()
    LOADING = auto()
    SUCCESS = auto()
    ERROR = auto()
    EMPTY = auto()


T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class UiState(Generic[T]):
    """
    Explicit UI state object replacing ad-hoc flags.

    Usage:
        state = UiState.loading()
        state = UiState.success(data=devices)
        state = UiState.error(message="Connection failed")
        state = UiState.empty(message="No devices found")
    """

    type: UiStateType
    data: Optional[Any] = None
    message: str = ""
    timestamp: datetime = field(default_factory=datetime.now)

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
    def is_idle(self) -> bool:
        return self.type == UiStateType.IDLE

    @property
    def has_data(self) -> bool:
        return self.data is not None

    # Factory methods
    @staticmethod
    def idle() -> "UiState":
        return UiState(type=UiStateType.IDLE)

    @staticmethod
    def loading(message: str = "Loading...") -> "UiState":
        return UiState(type=UiStateType.LOADING, message=message)

    @staticmethod
    def success(data: Any = None, message: str = "") -> "UiState":
        return UiState(type=UiStateType.SUCCESS, data=data, message=message)

    @staticmethod
    def error(message: str, data: Any = None) -> "UiState":
        return UiState(type=UiStateType.ERROR, data=data, message=message)

    @staticmethod
    def empty(message: str = "No data available") -> "UiState":
        return UiState(type=UiStateType.EMPTY, message=message)


# =============================================================================
# Base ViewModel
# =============================================================================


class BaseViewModel(QObject):
    """
    Base class for all ViewModels.

    Responsibilities:
    - Own and manage UI state
    - Expose reactive signals for Views to bind
    - Orchestrate Use Cases (Application Layer)
    - Transform data for UI consumption
    - Contain ZERO business rules

    Signals:
    - stateChanged: Emitted when UI state changes
    - errorOccurred: Emitted when an error occurs
    - loadingChanged: Emitted when loading state changes

    Usage:
        class DeviceListViewModel(BaseViewModel):
            devicesChanged = Signal(list)

            def load_devices(self):
                self._set_loading(True)
                # ... orchestrate use case
                self._set_state(UiState.success(data=devices))
    """

    # Core signals - all ViewModels emit these
    stateChanged = Signal(object)  # UiState
    errorOccurred = Signal(str)  # Error message
    loadingChanged = Signal(bool)  # Is loading

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self._state: UiState = UiState.idle()
        self._is_disposed = False
        self._subscriptions: List[Callable[[], None]] = []

    # -------------------------------------------------------------------------
    # State Management
    # -------------------------------------------------------------------------

    @property
    def state(self) -> UiState:
        """Get current UI state."""
        return self._state

    @property
    def is_loading(self) -> bool:
        """Check if currently loading."""
        return self._state.is_loading

    @property
    def has_error(self) -> bool:
        """Check if in error state."""
        return self._state.is_error

    @property
    def error_message(self) -> str:
        """Get current error message."""
        return self._state.message if self._state.is_error else ""

    def _set_state(self, new_state: UiState) -> None:
        """
        Update UI state and emit signals.

        This is the primary method for state updates.
        Views should bind to stateChanged signal.
        """
        if self._is_disposed:
            return

        old_state = self._state
        self._state = new_state

        # Emit state change
        self.stateChanged.emit(new_state)

        # Emit loading change if needed
        if old_state.is_loading != new_state.is_loading:
            self.loadingChanged.emit(new_state.is_loading)

        # Emit error if transitioning to error state
        if new_state.is_error and not old_state.is_error:
            self.errorOccurred.emit(new_state.message)

        logger.debug(f"[{self.__class__.__name__}] State: {old_state.type.name} -> {new_state.type.name}")

    def _set_loading(self, is_loading: bool, message: str = "Loading...") -> None:
        """Convenience method to set loading state."""
        if is_loading:
            self._set_state(UiState.loading(message))
        elif self._state.is_loading:
            self._set_state(UiState.idle())

    def _set_error(self, message: str) -> None:
        """Convenience method to set error state."""
        self._set_state(UiState.error(message))

    def _set_success(self, data: Any = None, message: str = "") -> None:
        """Convenience method to set success state."""
        self._set_state(UiState.success(data, message))

    def _set_empty(self, message: str = "No data available") -> None:
        """Convenience method to set empty state."""
        self._set_state(UiState.empty(message))

    # -------------------------------------------------------------------------
    # Subscription Management
    # -------------------------------------------------------------------------

    def add_subscription(self, unsubscribe: Callable[[], None]) -> None:
        """Track a subscription for cleanup."""
        self._subscriptions.append(unsubscribe)

    def _clear_subscriptions(self) -> None:
        """Clear all tracked subscriptions."""
        for unsub in self._subscriptions:
            try:
                unsub()
            except Exception as e:
                logger.warning(f"Error unsubscribing: {e}")
        self._subscriptions.clear()

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    def dispose(self) -> None:
        """
        Clean up ViewModel resources.

        Called when ViewModel is no longer needed.
        Subclasses should override and call super().
        """
        if self._is_disposed:
            return

        self._is_disposed = True
        self._clear_subscriptions()

        logger.debug(f"[{self.__class__.__name__}] Disposed")

    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize ViewModel.

        Called after construction to set up initial state.
        Subclasses must implement this.
        """
        pass


# =============================================================================
# Async ViewModel Mixin
# =============================================================================


class AsyncViewModelMixin:
    """
    Mixin for ViewModels that need async operations.

    Provides utilities for running async operations with proper
    state management and error handling.
    """

    def __init__(self):
        self._pending_operations: dict[str, bool] = {}

    def _is_operation_pending(self, operation_id: str) -> bool:
        """Check if an operation is pending."""
        return self._pending_operations.get(operation_id, False)

    def _mark_operation_started(self, operation_id: str) -> bool:
        """
        Mark an operation as started.

        Returns False if operation already pending (skip duplicate).
        """
        if self._pending_operations.get(operation_id, False):
            return False
        self._pending_operations[operation_id] = True
        return True

    def _mark_operation_completed(self, operation_id: str) -> None:
        """Mark an operation as completed."""
        self._pending_operations.pop(operation_id, None)

    def _cancel_all_operations(self) -> None:
        """Cancel all pending operations."""
        self._pending_operations.clear()


__all__ = [
    "UiState",
    "UiStateType",
    "BaseViewModel",
    "AsyncViewModelMixin",
]
