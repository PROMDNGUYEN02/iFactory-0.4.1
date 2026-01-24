"""
Base Presenter - Abstract Presenter with Clean Architecture.

Architectural Principles:
- Presenters transform data from Application layer to View layer
- NO Domain imports (only Application layer)
- NO Infrastructure imports
- NO business logic
- ONLY formatting and view-model construction
"""

from __future__ import annotations
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from PySide6.QtCore import QObject

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class BasePresenter(QObject, ABC):
    """
    Abstract Base Presenter.

    Responsibilities:
        - Transform Application DTOs/ViewModels to UI-ready formats
        - Handle legacy data format conversions (backward compatibility)
        - Provide UI-specific formatting (timestamps, colors, etc.)
        - NO business rules or logic

    Strict Constraints:
        ✅ Data formatting/transformation ONLY
        ✅ Application layer imports ONLY
        ✅ UI-specific logic (colors, labels, formatting)
        ❌ NO Domain layer imports
        ❌ NO Infrastructure layer imports
        ❌ NO business logic/rules
        ❌ NO data fetching (use UseCases)
        ❌ NO state management (use Views/Controllers)
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._theme = "light"
        logger.debug(f"[{self.__class__.__name__}] Created")

    @abstractmethod
    def set_theme(self, theme: str) -> None:
        """Set theme mode for formatting."""
        pass

    @abstractmethod
    def present(self, data: Any) -> Any:
        """
        Transform data for UI presentation.

        Args:
            data: Raw data from Application layer (DTO, ViewModel, etc.)

        Returns:
            UI-ready data (dict, ViewModel, formatted string, etc.)
        """
        pass

    def format_error(self, error: Exception) -> Dict[str, Any]:
        """
        Format error for UI display.

        Args:
            error: Exception instance

        Returns:
            Dictionary with error display information
        """
        return {
            "type": type(error).__name__,
            "message": str(error),
            "display_title": "Error",
            "display_message": f"An error occurred: {str(error)}",
            "is_critical": False,
        }

    def format_loading(self, message: str = "Loading...") -> Dict[str, Any]:
        """
        Format loading state for UI display.

        Args:
            message: Loading message

        Returns:
            Dictionary with loading state information
        """
        return {
            "type": "loading",
            "message": message,
            "is_loading": True,
        }

    def format_empty(self, message: str = "No data available") -> Dict[str, Any]:
        """
        Format empty state for UI display.

        Args:
            message: Empty state message

        Returns:
            Dictionary with empty state information
        """
        return {
            "type": "empty",
            "message": message,
            "is_empty": True,
        }


__all__ = ["BasePresenter"]
