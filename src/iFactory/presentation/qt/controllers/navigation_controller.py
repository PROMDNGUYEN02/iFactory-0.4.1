"""
Navigation Controller - Handles page navigation.

Fixed: Reverted __init__ signature to accept 'page_names' for backward compatibility with ui_container.py.
"""

from __future__ import annotations
import logging
from typing import List, Optional
from PySide6.QtCore import QObject, Signal

logger = logging.getLogger(__name__)


class NavigationController(QObject):
    """
    Controller for page navigation.

    Stores page names and current page state.
    UI management is handled by the container (ui_container.py).
    """

    page_changed = Signal(str)

    def __init__(self, page_names: List[str], default_page: str, parent: Optional[QObject] = None):
        """
        Initialize navigation controller.

        Args:
            page_names: List of available page names
            default_page: Default page to show
            parent: Qt parent
        """
        super().__init__(parent)
        self._page_names = page_names
        self._current_page = default_page
        self._history: List[str] = []
        logger.info(f"[NavigationController] Created (pages: {page_names}, default: {default_page})")

    def navigate_to(self, page_name: str) -> bool:
        """
        Navigate to page by name.

        Args:
            page_name: Page widget object name

        Returns:
            True if navigation successful
        """
        if page_name in self._page_names:
            old_page = self._current_page
            self._current_page = page_name
            if old_page and old_page != page_name:
                self._history.append(old_page)
            self.page_changed.emit(page_name)
            logger.debug(f"[NavigationController] Navigated: {old_page} → {page_name}")
            return True
        logger.warning(f"[NavigationController] Page not found: {page_name}")
        return False

    def go_back(self) -> bool:
        """Navigate to previous page in history."""
        if self._history:
            page = self._history.pop()
            return self.navigate_to(page)
        return False

    @property
    def current_page(self) -> str:
        """Get current page name."""
        return self._current_page

    @property
    def can_go_back(self) -> bool:
        """Check if can go back."""
        return len(self._history) > 0

    def get_all_pages(self) -> List[str]:
        """Get all page names."""
        return self._page_names.copy()


__all__ = ["NavigationController"]
