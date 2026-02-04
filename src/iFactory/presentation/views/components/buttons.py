# src/iFactory/presentation/views/components/buttons.py
"""
Enhanced Button components with animations and interactions.

Features:
- Ripple effect on click
- Hover animations
- Loading states
- Icon support
- Disabled state handling
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional, Union

from PySide6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QSize,
    QTimer,
    Property,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import QGraphicsDropShadowEffect, QPushButton, QWidget

from .base import (
    AnimationDuration,
    AnimationMixin,
    RippleEffectMixin,
    SpinnerWidget,
    ThemedButton,
)

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...resources.icons import Icons, DeviceIcons


class PrimaryButton(ThemedButton):
    """
    Primary action button with ripple effect.

    Features:
    - Material ripple on click
    - Hover elevation
    - Loading state with spinner
    """

    def __init__(self, text: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self._is_loading = False
        self._original_text = text

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_shadow()

    def _setup_shadow(self) -> None:
        """Setup hover shadow effect."""
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(0, 0, 0, 40))
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

    def enterEvent(self, event) -> None:
        if not self._is_loading:
            self._shadow.setBlurRadius(10)
            self._shadow.setOffset(0, 2)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._shadow.setBlurRadius(0)
        self._shadow.setOffset(0, 0)
        super().leaveEvent(event)

    def set_loading(self, loading: bool) -> None:
        """Toggle loading state."""
        self._is_loading = loading
        self.setEnabled(not loading)

        if loading:
            self.setText("Loading...")
            self.setCursor(Qt.CursorShape.WaitCursor)
        else:
            self.setText(self._original_text)
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
    """Danger/destructive action button with confirmation support."""

    confirm_clicked = Signal()

    def __init__(self, text: str, theme_service: "ThemeService", require_confirm: bool = False, parent: Optional[QWidget] = None):
        super().__init__(text, theme_service, parent)
        self._require_confirm = require_confirm
        self._is_confirming = False
        self._original_text = text
        self._confirm_timer: Optional[QTimer] = None

        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if self._require_confirm and event.button() == Qt.MouseButton.LeftButton:
            if not self._is_confirming:
                self._start_confirmation()
                return
            else:
                self.confirm_clicked.emit()
                self._cancel_confirmation()

        super().mousePressEvent(event)

    def _start_confirmation(self) -> None:
        """Start confirmation countdown."""
        self._is_confirming = True
        self.setText("Click again to confirm")

        self._confirm_timer = QTimer(self)
        self._confirm_timer.setSingleShot(True)
        self._confirm_timer.timeout.connect(self._cancel_confirmation)
        self._confirm_timer.start(3000)

    def _cancel_confirmation(self) -> None:
        """Cancel confirmation state."""
        self._is_confirming = False
        self.setText(self._original_text)

        if self._confirm_timer:
            self._confirm_timer.stop()
            self._confirm_timer = None

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


class IconButton(QPushButton, AnimationMixin):
    """
    Icon-only button with animations.

    Features:
    - Hover scale effect
    - Ripple on click
    - Tooltip support
    """

    def __init__(
        self,
        icon: Union["Icons", "DeviceIcons", str],
        theme_service: "ThemeService",
        size: int = 20,
        tooltip: str = "",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._theme_service = theme_service
        self._icon_ref = icon
        self._icon_size = size
        self._is_hovered = False

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(size + 12, size + 12)

        if tooltip:
            self.setToolTip(tooltip)

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

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        self._animate_scale(1.1)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        self._animate_scale(1.0)
        super().leaveEvent(event)

    def _animate_scale(self, scale: float) -> None:
        """Animate button scale."""
        target_size = int((self._icon_size + 12) * scale)

        # Simple size animation via stylesheet
        current = self.size()
        anim = QPropertyAnimation(self, b"iconSize")
        anim.setDuration(AnimationDuration.FAST)
        anim.setEndValue(QSize(int(self._icon_size * scale), int(self._icon_size * scale)))
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

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

    Features:
    - Animated icon transition
    - State persistence
    - Toggle signal
    """

    toggled = Signal(bool)

    def __init__(
        self,
        icon_on: Union["Icons", "DeviceIcons", str],
        icon_off: Union["Icons", "DeviceIcons", str],
        theme_service: "ThemeService",
        size: int = 20,
        initial_state: bool = False,
        tooltip_on: str = "",
        tooltip_off: str = "",
        parent: Optional[QWidget] = None,
    ):
        self._icon_on = icon_on
        self._icon_off = icon_off
        self._is_on = initial_state
        self._tooltip_on = tooltip_on
        self._tooltip_off = tooltip_off

        current_icon = icon_on if initial_state else icon_off
        current_tooltip = tooltip_on if initial_state else tooltip_off

        super().__init__(current_icon, theme_service, size, current_tooltip, parent)

        self.setCheckable(True)
        self.setChecked(initial_state)
        self.clicked.connect(self._on_clicked)

    def _on_clicked(self) -> None:
        self._is_on = self.isChecked()
        self._icon_ref = self._icon_on if self._is_on else self._icon_off

        # Update tooltip
        tooltip = self._tooltip_on if self._is_on else self._tooltip_off
        if tooltip:
            self.setToolTip(tooltip)

        # Animate icon change with rotation
        self._animate_toggle()
        self._load_icon()
        self.toggled.emit(self._is_on)

    def _animate_toggle(self) -> None:
        """Animate the toggle transition."""
        # Pulse animation
        if hasattr(self, "pulse"):
            self.pulse()

    @property
    def is_on(self) -> bool:
        return self._is_on

    def set_state(self, is_on: bool, animate: bool = True) -> None:
        """Programmatically set toggle state."""
        if is_on == self._is_on:
            return

        self._is_on = is_on
        self.setChecked(is_on)
        self._icon_ref = self._icon_on if is_on else self._icon_off

        tooltip = self._tooltip_on if is_on else self._tooltip_off
        if tooltip:
            self.setToolTip(tooltip)

        if animate:
            self._animate_toggle()

        self._load_icon()


class FloatingActionButton(QPushButton, AnimationMixin):
    """
    Material Design Floating Action Button (FAB).

    Features:
    - Circular design
    - Shadow elevation
    - Ripple effect
    - Mini variant
    """

    def __init__(self, icon: Union["Icons", "DeviceIcons", str], theme_service: "ThemeService", mini: bool = False, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._icon_ref = icon
        self._is_mini = mini

        size = 40 if mini else 56
        icon_size = 18 if mini else 24

        self.setFixedSize(size, size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self._setup_shadow()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()
        self._load_icon(icon_size)

    def _setup_shadow(self) -> None:
        """Setup elevation shadow."""
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(8)
        self._shadow.setColor(QColor(0, 0, 0, 60))
        self._shadow.setOffset(0, 4)
        self.setGraphicsEffect(self._shadow)

    def _load_icon(self, size: int) -> None:
        icon = self._theme_service.get_icon(self._icon_ref)
        if not icon.isNull():
            self.setIcon(icon)
            self.setIconSize(QSize(size, size))

    def enterEvent(self, event) -> None:
        self._shadow.setBlurRadius(12)
        self._shadow.setOffset(0, 6)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._shadow.setBlurRadius(8)
        self._shadow.setOffset(0, 4)
        super().leaveEvent(event)

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()
        icon_size = 18 if self._is_mini else 24
        self._load_icon(icon_size)

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens
        size = 40 if self._is_mini else 56

        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {tokens.primary};
                border: none;
                border-radius: {size // 2}px;
                color: {tokens.text_inverse};
            }}
            QPushButton:hover {{
                background-color: {tokens.primary_hover};
            }}
            QPushButton:pressed {{
                background-color: {tokens.primary_active};
            }}
        """
        )


class ButtonGroup(QWidget):
    """
    Group of buttons with mutual exclusion.

    Features:
    - Radio-style selection
    - Animated selection indicator
    - Horizontal/vertical layout
    """

    selection_changed = Signal(int, str)  # index, value

    def __init__(
        self,
        options: list[tuple[str, str]],  # [(value, label), ...]
        theme_service: "ThemeService",
        orientation: str = "horizontal",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._theme_service = theme_service
        self._options = options
        self._selected_index = 0
        self._buttons: list[QPushButton] = []

        self._setup_ui(orientation)
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def _setup_ui(self, orientation: str) -> None:
        from PySide6.QtWidgets import QHBoxLayout, QVBoxLayout

        if orientation == "horizontal":
            layout = QHBoxLayout(self)
        else:
            layout = QVBoxLayout(self)

        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        for i, (value, label) in enumerate(self._options):
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setChecked(i == 0)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=i: self._on_button_clicked(idx))

            self._buttons.append(btn)
            layout.addWidget(btn)

    def _on_button_clicked(self, index: int) -> None:
        if index == self._selected_index:
            # Keep button checked
            self._buttons[index].setChecked(True)
            return

        # Uncheck previous
        self._buttons[self._selected_index].setChecked(False)

        # Check new
        self._selected_index = index
        self._buttons[index].setChecked(True)

        value = self._options[index][0]
        self.selection_changed.emit(index, value)

    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        tokens = self._theme_service.tokens

        for i, btn in enumerate(self._buttons):
            # Determine border radius based on position
            if i == 0:
                radius = f"{tokens.radius_md} 0 0 {tokens.radius_md}"
            elif i == len(self._buttons) - 1:
                radius = f"0 {tokens.radius_md} {tokens.radius_md} 0"
            else:
                radius = "0"

            btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {tokens.surface_card};
                    border: 1px solid {tokens.border_default};
                    border-radius: {radius};
                    padding: {tokens.space_2} {tokens.space_3};
                    color: {tokens.text_secondary};
                    font-size: {tokens.font_size_sm};
                    min-width: 60px;
                }}
                QPushButton:checked {{
                    background-color: {tokens.primary};
                    border-color: {tokens.primary};
                    color: {tokens.text_inverse};
                }}
                QPushButton:hover:!checked {{
                    background-color: {tokens.interactive_hover};
                }}
            """
            )

    def get_selected_value(self) -> str:
        return self._options[self._selected_index][0]

    def set_selected_index(self, index: int) -> None:
        if 0 <= index < len(self._buttons):
            self._on_button_clicked(index)


__all__ = [
    "PrimaryButton",
    "SecondaryButton",
    "GhostButton",
    "DangerButton",
    "SuccessButton",
    "IconButton",
    "ToggleIconButton",
    "FloatingActionButton",
    "ButtonGroup",
]
