# File: presentation/views/components/inputs.py
"""
Input field components.

Usage:
    search = SearchInput(theme_service, placeholder="Search devices...")
    text = TextInput(theme_service, placeholder="Enter name")
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import QLineEdit, QHBoxLayout, QWidget

from ...resources.icons import Icons

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class TextInput(QLineEdit):
    """
    Themed text input field.

    Usage:
        input = TextInput(theme_service, placeholder="Enter value")
    """

    def __init__(self, theme_service: "ThemeService", placeholder: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service

        self.setPlaceholderText(placeholder)
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_base};
                padding: {tokens.space_2} {tokens.space_3};
                min-height: {tokens.size_input_height};
                color: {tokens.text_primary};
                font-size: {tokens.font_size_base};
                selection-background-color: {tokens.primary_subtle};
            }}
            QLineEdit:hover {{
                border-color: {tokens.border_strong};
            }}
            QLineEdit:focus {{
                border-color: {tokens.border_focus};
                outline: none;
            }}
            QLineEdit:disabled {{
                background-color: {tokens.interactive_disabled_bg};
                color: {tokens.interactive_disabled_text};
            }}
            QLineEdit::placeholder {{
                color: {tokens.text_muted};
            }}
        """
        )


class SearchInput(QWidget):
    """
    Search input with icon and clear button.

    Usage:
        search = SearchInput(theme_service, placeholder="Search...")
        search.textChanged.connect(on_search)
    """

    textChanged = Signal(str)
    returnPressed = Signal()

    def __init__(self, theme_service: "ThemeService", placeholder: str = "Search...", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service

        self._setup_ui(placeholder)
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self, placeholder: str) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.textChanged.connect(self.textChanged.emit)
        self._input.returnPressed.connect(self.returnPressed.emit)

        layout.addWidget(self._input)

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens

        self._input.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
                padding: {tokens.space_2} {tokens.space_3};
                padding-left: {tokens.space_8};
                min-height: {tokens.size_input_height};
                color: {tokens.text_primary};
                font-size: {tokens.font_size_base};
            }}
            QLineEdit:hover {{
                border-color: {tokens.border_strong};
            }}
            QLineEdit:focus {{
                border-color: {tokens.border_focus};
            }}
            QLineEdit::placeholder {{
                color: {tokens.text_muted};
            }}
        """
        )

    def text(self) -> str:
        return self._input.text()

    def setText(self, text: str) -> None:
        self._input.setText(text)

    def clear(self) -> None:
        self._input.clear()

    def setPlaceholderText(self, text: str) -> None:
        self._input.setPlaceholderText(text)


__all__ = [
    "TextInput",
    "SearchInput",
]
