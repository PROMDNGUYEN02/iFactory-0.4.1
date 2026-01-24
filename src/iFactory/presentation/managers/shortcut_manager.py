# File: src/iFactory/presentation/managers/shortcut_manager.py
"""
Shortcut Manager - Manages keyboard shortcuts.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, List, Dict

from PySide6.QtCore import QObject
from PySide6.QtGui import QKeySequence, QShortcut


@dataclass
class ShortcutDefinition:
    """Shortcut definition."""

    key: str
    callback: Callable[[], None]
    description: str = ""
    enabled: bool = True


class ShortcutManager(QObject):
    """Manages keyboard shortcuts."""

    __slots__ = ("_parent", "_shortcuts", "_destroyed")

    def __init__(self, parent: QObject):
        super().__init__(parent)
        self._parent = parent
        self._shortcuts: Dict[str, tuple[QShortcut, ShortcutDefinition]] = {}
        self._destroyed = False

    def register(
        self, key: str, callback: Callable[[], None], description: str = ""
    ) -> None:
        """Register a keyboard shortcut."""
        if key in self._shortcuts:
            self.unregister(key)

        definition = ShortcutDefinition(
            key=key, callback=callback, description=description
        )
        shortcut = QShortcut(QKeySequence(key), self._parent)
        shortcut.activated.connect(self._safe_call(callback))
        self._shortcuts[key] = (shortcut, definition)

    def register_multiple(
        self, shortcuts: List[tuple[str, Callable[[], None], str]]
    ) -> None:
        """Register multiple shortcuts."""
        for key, cb, desc in shortcuts:
            self.register(key, cb, desc)

    def register_page_shortcuts(
        self, go_to_page: Callable[[int], None], max_pages: int = 9
    ) -> None:
        """Register Ctrl+1~9 page shortcuts."""
        for i in range(1, min(max_pages + 1, 10)):
            self.register(
                f"Ctrl+{i}", lambda idx=i - 1: go_to_page(idx), f"Go to page {i}"
            )

    def unregister(self, key: str) -> bool:
        """Unregister a shortcut."""
        if key in self._shortcuts:
            (sc, _) = self._shortcuts.pop(key)
            sc.setEnabled(False)
            sc.deleteLater()
            return True
        return False

    def _safe_call(self, callback: Callable[[], None]) -> Callable[[], None]:
        """Create safe callback wrapper."""

        def wrapper():
            if not self._destroyed:
                try:
                    callback()
                except Exception as e:
                    print(f"Shortcut error: {e}")  # Fallback logging

        return wrapper

    def set_enabled(self, key: str, enabled: bool) -> None:
        """Set shortcut enabled state."""
        if key in self._shortcuts:
            (sc, defn) = self._shortcuts[key]
            sc.setEnabled(enabled)
            defn.enabled = enabled

    def set_all_enabled(self, enabled: bool) -> None:
        """Set all shortcuts enabled state."""
        for sc, defn in self._shortcuts.values():
            sc.setEnabled(enabled)
            defn.enabled = enabled

    def get_help_text(self) -> str:
        """Get help text with all shortcuts."""
        lines = ["Keyboard Shortcuts:", "─" * 30]
        for key, (_, defn) in sorted(self._shortcuts.items()):
            lines.append(f"{key:<20} {defn.description or key}")
        return "\n".join(lines)

    def cleanup(self) -> None:
        """Cleanup all shortcuts."""
        self._destroyed = True
        for key in list(self._shortcuts.keys()):
            self.unregister(key)


def create_standard_shortcuts(
    manager: ShortcutManager, handlers: Dict[str, Callable[[], None]]
) -> None:
    """Create standard application shortcuts."""
    shortcuts = [
        ("Escape", handlers.get("escape", lambda: None), "Close/Exit"),
        ("F11", handlers.get("fullscreen", lambda: None), "Toggle Fullscreen"),
        ("F1", handlers.get("info", lambda: None), "Show Information"),
        ("Ctrl+Tab", handlers.get("next_page", lambda: None), "Next Page"),
        ("Ctrl+Shift+Tab", handlers.get("prev_page", lambda: None), "Previous Page"),
        ("Ctrl+Shift+T", handlers.get("toggle_theme", lambda: None), "Toggle Theme"),
        ("Ctrl+L", handlers.get("toggle_left_menu", lambda: None), "Toggle Left Menu"),
        (
            "Ctrl+R",
            handlers.get("toggle_right_menu", lambda: None),
            "Toggle Right Menu",
        ),
        ("Ctrl+,", handlers.get("toggle_settings", lambda: None), "Settings"),
        ("Ctrl+E", handlers.get("toggle_edit_mode", lambda: None), "Edit Positions"),
    ]
    manager.register_multiple(shortcuts)
    if go_to := handlers.get("go_to_page"):
        manager.register_page_shortcuts(go_to)
