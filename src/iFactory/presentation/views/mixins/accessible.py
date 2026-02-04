# presentation/views/mixins/accessible.py
"""
Accessibility Mixins for WCAG compliance.

Features:
- Keyboard navigation
- Screen reader support
- Focus management
- High contrast mode
"""

from __future__ import annotations

from typing import Optional, List, Callable
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QApplication
from PySide6.QtGui import QKeyEvent, QFocusEvent


class KeyboardNavigableMixin:
    """
    Mixin for keyboard navigation support.

    Features:
    - Arrow key navigation
    - Enter/Space activation
    - Escape to cancel
    - Tab order management
    """

    # Override in subclass
    _navigable_items: List[QWidget] = []
    _current_focus_index: int = -1

    def setup_keyboard_navigation(
        self,
        items: List[QWidget],
        wrap: bool = True,
        on_activate: Optional[Callable[[QWidget], None]] = None,
    ) -> None:
        """Setup keyboard navigation for list of items."""
        self._navigable_items = items
        self._wrap = wrap
        self._on_activate = on_activate
        self._current_focus_index = -1

        # Make items focusable
        for item in items:
            item.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        key = event.key()

        if key in (Qt.Key.Key_Up, Qt.Key.Key_Left):
            self._navigate(-1)
            event.accept()
            return

        if key in (Qt.Key.Key_Down, Qt.Key.Key_Right):
            self._navigate(1)
            event.accept()
            return

        if key == Qt.Key.Key_Home:
            self._navigate_to(0)
            event.accept()
            return

        if key == Qt.Key.Key_End:
            self._navigate_to(len(self._navigable_items) - 1)
            event.accept()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self._activate_current()
            event.accept()
            return

        # Call parent
        super().keyPressEvent(event)

    def _navigate(self, delta: int) -> None:
        """Navigate by delta items."""
        if not self._navigable_items:
            return

        new_index = self._current_focus_index + delta

        if self._wrap:
            new_index = new_index % len(self._navigable_items)
        else:
            new_index = max(0, min(new_index, len(self._navigable_items) - 1))

        self._navigate_to(new_index)

    def _navigate_to(self, index: int) -> None:
        """Navigate to specific index."""
        if not 0 <= index < len(self._navigable_items):
            return

        self._current_focus_index = index
        self._navigable_items[index].setFocus()

    def _activate_current(self) -> None:
        """Activate currently focused item."""
        if self._current_focus_index >= 0 and self._on_activate:
            item = self._navigable_items[self._current_focus_index]
            self._on_activate(item)


class FocusTrapMixin:
    """
    Mixin for trapping focus within a container (modals, dialogs).
    """

    _first_focusable: Optional[QWidget] = None
    _last_focusable: Optional[QWidget] = None

    def setup_focus_trap(self, container: QWidget) -> None:
        """Setup focus trap within container."""
        focusable = self._find_focusable_children(container)

        if focusable:
            self._first_focusable = focusable[0]
            self._last_focusable = focusable[-1]
            self._first_focusable.setFocus()

    def _find_focusable_children(self, widget: QWidget) -> List[QWidget]:
        """Find all focusable children."""
        focusable = []

        for child in widget.findChildren(QWidget):
            policy = child.focusPolicy()
            if policy in (
                Qt.FocusPolicy.TabFocus,
                Qt.FocusPolicy.StrongFocus,
                Qt.FocusPolicy.WheelFocus,
            ):
                if child.isEnabled() and child.isVisible():
                    focusable.append(child)

        return focusable

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key.Key_Tab:
            current = QApplication.focusWidget()

            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                # Shift+Tab - going backwards
                if current == self._first_focusable:
                    self._last_focusable.setFocus()
                    event.accept()
                    return
            else:
                # Tab - going forwards
                if current == self._last_focusable:
                    self._first_focusable.setFocus()
                    event.accept()
                    return

        super().keyPressEvent(event)


class AccessibleWidgetMixin:
    """
    Mixin for screen reader accessibility.

    Provides:
    - Accessible name and description
    - Role announcement
    - State changes
    """

    def set_accessible_info(
        self,
        name: str,
        description: str = "",
        role: str = "",
    ) -> None:
        """Set accessibility information."""
        if hasattr(self, "setAccessibleName"):
            self.setAccessibleName(name)

        if hasattr(self, "setAccessibleDescription") and description:
            self.setAccessibleDescription(description)

        # Store role for custom handling
        self._accessible_role = role

    def announce(self, message: str, priority: str = "polite") -> None:
        """
        Announce message to screen reader.

        Note: Full implementation would use platform-specific APIs
        or ARIA-like live regions.
        """
        # For now, update accessible description
        if hasattr(self, "setAccessibleDescription"):
            self.setAccessibleDescription(message)


class HighContrastMixin:
    """
    Mixin for high contrast mode support.
    """

    _is_high_contrast: bool = False

    @property
    def is_high_contrast(self) -> bool:
        return self._is_high_contrast

    def set_high_contrast(self, enabled: bool) -> None:
        """Toggle high contrast mode."""
        self._is_high_contrast = enabled
        self._apply_high_contrast_style()

    def _apply_high_contrast_style(self) -> None:
        """Apply high contrast styles - override in subclass."""
        pass

    def _get_high_contrast_colors(self) -> dict:
        """Get high contrast color palette."""
        return {
            "background": "#000000",
            "foreground": "#FFFFFF",
            "primary": "#FFFF00",
            "error": "#FF0000",
            "success": "#00FF00",
            "border": "#FFFFFF",
            "focus": "#00FFFF",
        }


__all__ = [
    "KeyboardNavigableMixin",
    "FocusTrapMixin",
    "AccessibleWidgetMixin",
    "HighContrastMixin",
]
