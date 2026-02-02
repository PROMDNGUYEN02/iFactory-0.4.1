# File: presentation/views/components/buttons.py
"""
Button components with consistent theming.

Usage:
    btn = PrimaryButton("Save", theme_service)
    btn = GhostButton("Cancel", theme_service)
    btn = IconButton(Icons.SETTINGS, theme_service)
    btn = DangerButton("Delete", theme_service)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QPushButton, QWidget

from .base import ThemedButton

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...resources.icons import Icons, DeviceIcons


class PrimaryButton(ThemedButton):
    """Primary action button with accent color."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {tokens.primary};
                border: 1px solid {tokens.primary};
                border-radius: {tokens.radius_md};
                padding: {tokens.space_2} {tokens.space_4};
                min-height: {tokens.size_button_height_base};
                color: {tokens.text_inverse};
                font-weight: {tokens.font_weight_medium};
                font-size: {tokens.font_size_base};
            }}
            QPushButton:hover {{
                background-color: {tokens.primary_hover};
                border-color: {tokens.primary_hover};
            }}
            QPushButton:pressed {{
                background-color: {tokens.primary_active};
            }}
            QPushButton:disabled {{
                background-color: {tokens.interactive_disabled_bg};
                color: {tokens.interactive_disabled_text};
                border-color: {tokens.border_subtle};
            }}
        """
        )


class SecondaryButton(ThemedButton):
    """Secondary button with outline style."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: 1px solid {tokens.primary};
                border-radius: {tokens.radius_md};
                padding: {tokens.space_2} {tokens.space_4};
                min-height: {tokens.size_button_height_base};
                color: {tokens.primary};
                font-weight: {tokens.font_weight_medium};
                font-size: {tokens.font_size_base};
            }}
            QPushButton:hover {{
                background-color: {tokens.primary_subtle};
            }}
            QPushButton:pressed {{
                background-color: {tokens.primary_subtle};
            }}
            QPushButton:disabled {{
                border-color: {tokens.interactive_disabled_text};
                color: {tokens.interactive_disabled_text};
            }}
        """
        )


class GhostButton(ThemedButton):
    """Ghost button with transparent background."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: {tokens.radius_md};
                padding: {tokens.space_2} {tokens.space_4};
                min-height: {tokens.size_button_height_base};
                color: {tokens.text_secondary};
                font-weight: {tokens.font_weight_medium};
                font-size: {tokens.font_size_base};
            }}
            QPushButton:hover {{
                background-color: {tokens.interactive_hover};
                color: {tokens.text_primary};
            }}
            QPushButton:pressed {{
                background-color: {tokens.interactive_active};
            }}
            QPushButton:disabled {{
                color: {tokens.interactive_disabled_text};
            }}
        """
        )


class DangerButton(ThemedButton):
    """Danger/destructive action button."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {tokens.error};
                border: 1px solid {tokens.error};
                border-radius: {tokens.radius_md};
                padding: {tokens.space_2} {tokens.space_4};
                min-height: {tokens.size_button_height_base};
                color: {tokens.text_inverse};
                font-weight: {tokens.font_weight_medium};
            }}
            QPushButton:hover {{
                background-color: {tokens.error_hover};
                border-color: {tokens.error_hover};
            }}
            QPushButton:disabled {{
                background-color: {tokens.interactive_disabled_bg};
                color: {tokens.interactive_disabled_text};
                border-color: {tokens.border_subtle};
            }}
        """
        )


class SuccessButton(ThemedButton):
    """Success/confirm action button."""

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {tokens.success};
                border: 1px solid {tokens.success};
                border-radius: {tokens.radius_md};
                padding: {tokens.space_2} {tokens.space_4};
                min-height: {tokens.size_button_height_base};
                color: {tokens.text_inverse};
                font-weight: {tokens.font_weight_medium};
            }}
            QPushButton:hover {{
                background-color: {tokens.success_hover};
                border-color: {tokens.success_hover};
            }}
            QPushButton:disabled {{
                background-color: {tokens.interactive_disabled_bg};
                color: {tokens.interactive_disabled_text};
                border-color: {tokens.border_subtle};
            }}
        """
        )


class IconButton(QPushButton):
    """
    Icon-only button with theme support.

    Usage:
        btn = IconButton(Icons.SETTINGS, theme_service)
        btn = IconButton(Icons.CLOSE, theme_service, size=24)
    """

    def __init__(self, icon: Union["Icons", "DeviceIcons", str], theme_service: "ThemeService", size: int = 20, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._icon_ref = icon
        self._icon_size = size

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(size + 12, size + 12)

        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()
        self._load_icon()

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()
        self._load_icon()

    def _load_icon(self) -> None:
        """Load icon from ThemeService."""
        icon = self._theme_service.get_icon(self._icon_ref)
        if not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(QSize(self._icon_size, self._icon_size))

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: transparent;
                border: none;
                border-radius: {tokens.radius_base};
                padding: {tokens.space_1};
            }}
            QPushButton:hover {{
                background-color: {tokens.interactive_hover};
            }}
            QPushButton:pressed {{
                background-color: {tokens.interactive_active};
            }}
            QPushButton:disabled {{
                opacity: 0.5;
            }}
        """
        )

    def set_icon(self, icon: Union["Icons", "DeviceIcons", str]) -> None:
        """Change the button icon."""
        self._icon_ref = icon
        self._load_icon()


class ToggleIconButton(IconButton):
    """
    Icon button that toggles between two states.

    Usage:
        btn = ToggleIconButton(
            icon_on=Icons.MOON,
            icon_off=Icons.SUN,
            theme_service=theme_service
        )
        btn.toggled.connect(on_toggle)
    """

    def __init__(
        self,
        icon_on: Union["Icons", "DeviceIcons", str],
        icon_off: Union["Icons", "DeviceIcons", str],
        theme_service: "ThemeService",
        size: int = 20,
        initial_state: bool = False,
        parent: Optional[QWidget] = None,
    ):
        self._icon_on = icon_on
        self._icon_off = icon_off
        self._is_on = initial_state

        current_icon = icon_on if initial_state else icon_off
        super().__init__(current_icon, theme_service, size, parent)

        self.setCheckable(True)
        self.setChecked(initial_state)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._is_on = self.isChecked()
        self._icon_ref = self._icon_on if self._is_on else self._icon_off
        self._load_icon()

    @property
    def is_on(self) -> bool:
        return self._is_on

    def set_state(self, is_on: bool) -> None:
        """Programmatically set toggle state."""
        self._is_on = is_on
        self.setChecked(is_on)
        self._icon_ref = self._icon_on if is_on else self._icon_off
        self._load_icon()


__all__ = [
    "PrimaryButton",
    "SecondaryButton",
    "GhostButton",
    "DangerButton",
    "SuccessButton",
    "IconButton",
    "ToggleIconButton",
]
