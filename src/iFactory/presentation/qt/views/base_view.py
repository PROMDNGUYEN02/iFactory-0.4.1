"""
Base View - Abstract View with Clear Boundaries.

Architectural Principles:
- Views render UI ONLY
- NO business logic
- NO data transformation (use Presenters)
- NO application calls (use Controllers)
- Signal/event emission ONLY for user actions
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from iFactory.presentation.qt.controllers.base_controller import BaseController

logger = logging.getLogger(__name__)


class BaseView(QWidget, ABC):
    """
    Abstract Base View.

    Responsibilities:
        - Render UI components
        - Display data from Presenters/Controllers
        - Emit signals for user interactions
        - Handle UI state (visibility, selection, focus)

    Strict Constraints:
        ✅ UI rendering ONLY
        ✅ Display data from Presenters/Controllers
        ✅ Emit signals for user actions
        ✅ Handle UI state (visibility, focus, selection)
        ❌ NO business logic
        ❌ NO data transformation (use Presenters)
        ❌ NO application/service calls (use Controllers)
        ❌ NO domain/application imports
        ❌ NO controller logic in view
    """

    data_requested = Signal(str)
    action_triggered = Signal(str, dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._controller: Optional[BaseController] = None
        self._state: Dict[str, Any] = {}
        self._initialized = False
        logger.debug(f"[{self.__class__.__name__}] Created")

    @abstractmethod
    def setup_ui(self) -> None:
        """Setup UI components and layout."""
        pass

    @abstractmethod
    def update_display(self, data: Any) -> None:
        """
        Update UI display with new data.

        Args:
            data: Formatted data from Presenter/Controller
        """
        pass

    def set_controller(self, controller: BaseController) -> None:
        """Set controller reference and connect signals."""
        self._controller = controller
        self._connect_controller_signals()
        logger.debug(f"[{self.__class__.__name__}] Controller set")

    def _connect_controller_signals(self) -> None:
        """Connect controller signals to view slots. Override in subclasses."""
        pass

    def emit_data_request(self, request_type: str, **kwargs: Any) -> None:
        """
        Emit data request to controller.

        Args:
            request_type: Type of data requested
            **kwargs: Additional parameters for the request
        """
        self.data_requested.emit(request_type, kwargs)

    def emit_action(self, action_name: str, params: Dict[str, Any]) -> None:
        """
        Emit user action to controller.

        Args:
            action_name: Name of the action
            params: Action parameters
        """
        self.action_triggered.emit(action_name, params)

    def show_loading(self, message: str = "Loading...") -> None:
        """Show loading state. Override in subclasses."""
        pass

    def show_empty(self, message: str = "No data available") -> None:
        """Show empty state. Override in subclasses."""
        pass

    def show_error(self, title: str, message: str) -> None:
        """Show error state. Override in subclasses."""
        pass

    @property
    def is_initialized(self) -> bool:
        """Check if view is initialized."""
        return self._initialized


__all__ = ["BaseView"]
