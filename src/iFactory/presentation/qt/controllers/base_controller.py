"""
Base Controller - Abstract Controller with Clear Boundaries.

Architectural Principles:
- Controllers orchestrate UseCases and Presenters only
- NO UI state management
- NO business logic
- NO data transformation (delegated to Presenters)
- NO domain imports (only Application layer)
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from iFactory.presentation.qt.presenters.base_presenter import BasePresenter
    from iFactory.presentation.qt.views.base_view import BaseView

logger = logging.getLogger(__name__)


class BaseController(QObject, ABC):
    """
    Abstract Base Controller.

    Responsibilities:
        - Orchestrate Application UseCases
        - Coordinate Presenters for data transformation
        - Emit signals to Views
        - Handle external events and route to appropriate handlers

    Strict Constraints:
        ✅ Orchestration ONLY
        ✅ Signal emission ONLY
        ✅ Application layer imports ONLY
        ❌ NO UI state management
        ❌ NO business logic
        ❌ NO data transformation (use Presenters)
        ❌ NO Domain layer imports
        ❌ NO Infrastructure layer imports
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._presenters: Dict[str, BasePresenter] = {}
        self._use_cases: Dict[str, Any] = {}
        self._initialized = False
        logger.debug(f"[{self.__class__.__name__}] Created")

    @abstractmethod
    def initialize(self) -> None:
        """Initialize controller and dependencies."""
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown controller and cleanup."""
        pass

    def register_presenter(self, name: str, presenter: BasePresenter) -> None:
        """Register a presenter by name."""
        self._presenters[name] = presenter
        logger.debug(f"[{self.__class__.__name__}] Registered presenter: {name}")

    def register_use_case(self, name: str, use_case: Any) -> None:
        """Register a use case by name."""
        self._use_cases[name] = use_case
        logger.debug(f"[{self.__class__.__name__}] Registered use case: {name}")

    def get_presenter(self, name: str) -> Optional[BasePresenter]:
        """Get registered presenter by name."""
        return self._presenters.get(name)

    def get_use_case(self, name: str) -> Optional[Any]:
        """Get registered use case by name."""
        return self._use_cases.get(name)

    def emit_state(self, state_name: str, data: Any) -> None:
        """
        Emit a state change to connected views.

        This is the ONLY way controllers should communicate with views.
        Views should listen to signals and update accordingly.
        """
        if not hasattr(self, state_name):
            logger.warning(f"[{self.__class__.__name__}] Signal not found: {state_name}")
            return
        signal = getattr(self, state_name)
        if isinstance(signal, Signal):
            signal.emit(data)
        else:
            logger.warning(f"[{self.__class__.__name__}] Not a signal: {state_name}")

    @property
    def is_initialized(self) -> bool:
        """Check if controller is initialized."""
        return self._initialized


__all__ = ["BaseController"]
