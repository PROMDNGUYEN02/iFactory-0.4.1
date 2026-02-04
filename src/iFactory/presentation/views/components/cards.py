# src/iFactory/presentation/views/components/cards.py
"""
Enhanced Card components with animations and micro-interactions.

New Features:
- Hover lift effect with shadow
- Click ripple effect
- Loading skeleton states
- Animated value changes
- Error states
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import (
    QEasingCurve,
    QPropertyAnimation,
    QTimer,
    Property,
    Qt,
    Signal,
)
from PySide6.QtGui import QColor, QPainter, QPainterPath
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from .base import (
    AnimationDuration,
    AnimationMixin,
    HoverEffectMixin,
    SkeletonLoader,
    ThemedFrame,
)
from .progress import AnimatedProgressBar

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class Card(ThemedFrame, HoverEffectMixin):
    """
    Basic card container with hover effects.

    Features:
    - Shadow on hover
    - Smooth transitions
    - Theme-aware styling
    """

    def __init__(self, theme_service: "ThemeService", hover_lift: bool = True, parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._hover_lift = hover_lift

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        if hover_lift:
            self._setup_shadow()

    def _setup_shadow(self) -> None:
        """Setup hover shadow effect."""
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(0, 0, 0, 40))
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

        self._shadow_anim = QPropertyAnimation(self._shadow, b"blurRadius")
        self._shadow_anim.setDuration(AnimationDuration.FAST)
        self._shadow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def enterEvent(self, event) -> None:
        if self._hover_lift and hasattr(self, "_shadow_anim"):
            self._shadow_anim.stop()
            self._shadow_anim.setStartValue(self._shadow.blurRadius())
            self._shadow_anim.setEndValue(20)
            self._shadow_anim.start()
            self._shadow.setOffset(0, 4)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if self._hover_lift and hasattr(self, "_shadow_anim"):
            self._shadow_anim.stop()
            self._shadow_anim.setStartValue(self._shadow.blurRadius())
            self._shadow_anim.setEndValue(0)
            self._shadow_anim.start()
            self._shadow.setOffset(0, 0)
        super().leaveEvent(event)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            Card {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_lg};
            }}
        """
        )

    def set_padding(self, padding: int) -> None:
        self._layout.setContentsMargins(padding, padding, padding, padding)

    def set_spacing(self, spacing: int) -> None:
        self._layout.setSpacing(spacing)


class ElevatedCard(ThemedFrame, HoverEffectMixin):
    """Card with permanent elevation and hover effect."""

    def __init__(self, theme_service: "ThemeService", elevation: int = 2, parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._elevation = elevation

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        self._setup_shadow()

    def _setup_shadow(self) -> None:
        """Setup permanent shadow."""
        self._shadow = QGraphicsDropShadowEffect(self)
        blur = 8 * self._elevation
        offset = 2 * self._elevation
        self._shadow.setBlurRadius(blur)
        self._shadow.setColor(QColor(0, 0, 0, 30))
        self._shadow.setOffset(0, offset)
        self.setGraphicsEffect(self._shadow)

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self.setStyleSheet(
            f"""
            ElevatedCard {{
                background-color: {tokens.surface_elevated};
                border: 1px solid {tokens.border_subtle};
                border-radius: {tokens.radius_lg};
            }}
        """
        )


class StatCard(ThemedFrame, HoverEffectMixin):
    """
    Enhanced statistics card with animations.

    Features:
    - Animated value changes
    - Color-coded indicator
    - Progress bar animation
    - Loading skeleton state
    - Click feedback
    """

    clicked = Signal()
    value_changed = Signal(str, float)

    def __init__(self, title: str, theme_service: "ThemeService", color: str = "primary", parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._title = title
        self._color = color
        self._color_value = self._get_color_value()
        self._current_value = 0.0
        self._is_loading = False

        self._setup_ui()
        self._setup_shadow()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_shadow(self) -> None:
        """Setup hover shadow."""
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(0, 0, 0, 30))
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

    def _get_color_value(self) -> str:
        tokens = self.tokens
        color_map = {
            "primary": tokens.primary,
            "success": tokens.success,
            "warning": tokens.warning,
            "error": tokens.error,
            "info": tokens.info,
        }
        return color_map.get(self._color, tokens.primary)

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Color indicator bar
        self._indicator = QFrame()
        self._indicator.setFixedSize(3, 28)
        layout.addWidget(self._indicator)

        # Content container
        self._content = QWidget()
        content_layout = QVBoxLayout(self._content)
        content_layout.setSpacing(4)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Title and value row
        row = QHBoxLayout()
        row.setSpacing(8)

        self._title_label = QLabel(self._title)
        row.addWidget(self._title_label)

        self._value_label = QLabel("--")
        self._value_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        row.addWidget(self._value_label)

        content_layout.addLayout(row)

        # Progress bar
        self._progress = AnimatedProgressBar(self._color_value, self._theme_service)
        content_layout.addWidget(self._progress)

        layout.addWidget(self._content, 1)

        # Skeleton loader (hidden by default)
        self._skeleton = SkeletonLoader(width=80, height=16, parent=self)
        self._skeleton.hide()

    def _apply_theme(self) -> None:
        tokens = self.tokens
        self._color_value = self._get_color_value()

        self.setStyleSheet(
            f"""
            StatCard {{
                background: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
            }}
            StatCard:hover {{
                border-color: {tokens.border_strong};
            }}
        """
        )

        self._indicator.setStyleSheet(
            f"""
            background-color: {self._color_value};
            border-radius: 1px;
        """
        )

        self._title_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )

        self._value_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            font-weight: {tokens.font_weight_bold};
            color: {self._color_value};
        """
        )

    def set_value(self, display: str, percent: float) -> None:
        """Set value with animation."""
        if self._is_loading:
            self.set_loading(False)

        old_value = self._current_value
        self._current_value = percent

        # Animate value label (fade effect)
        self._value_label.setText(display)

        # Animate progress bar
        self._progress.animate_to(percent)

        self.value_changed.emit(display, percent)

    def set_loading(self, loading: bool) -> None:
        """Toggle loading skeleton state."""
        self._is_loading = loading

        if loading:
            self._content.hide()
            self._skeleton.show()
        else:
            self._skeleton.hide()
            self._skeleton.stop()
            self._content.show()

    def enterEvent(self, event) -> None:
        if hasattr(self, "_shadow"):
            self._shadow.setBlurRadius(12)
            self._shadow.setOffset(0, 3)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if hasattr(self, "_shadow"):
            self._shadow.setBlurRadius(0)
            self._shadow.setOffset(0, 0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            # Brief scale animation for feedback
            if hasattr(self, "pulse"):
                self.pulse()
        super().mousePressEvent(event)


class DeviceCard(ThemedFrame, HoverEffectMixin):
    """
    Enhanced device card with animations and states.

    Features:
    - Hover lift effect
    - Status indicator animation
    - Click/double-click handling
    - Loading state
    - Error state
    """

    clicked = Signal(str)
    double_clicked = Signal(str)

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(theme_service, parent)
        self._device_id = ""
        self._is_loading = False
        self._has_error = False

        self._setup_ui()
        self._setup_shadow()
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def _setup_shadow(self) -> None:
        """Setup hover shadow."""
        self._shadow = QGraphicsDropShadowEffect(self)
        self._shadow.setBlurRadius(0)
        self._shadow.setColor(QColor(0, 0, 0, 30))
        self._shadow.setOffset(0, 0)
        self.setGraphicsEffect(self._shadow)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        # Header row
        header = QHBoxLayout()
        header.setSpacing(8)

        self._icon_label = QLabel()
        self._icon_label.setFixedSize(32, 32)
        header.addWidget(self._icon_label)

        self._name_label = QLabel("--")
        self._name_label.setObjectName("device_name")
        header.addWidget(self._name_label, 1)

        # Animated status dot
        self._status_dot = StatusDot(self._theme_service)
        header.addWidget(self._status_dot)

        layout.addLayout(header)

        # Status label
        self._status_label = QLabel("Unknown")
        self._status_label.setObjectName("device_status")
        layout.addWidget(self._status_label)

        # Skeleton loader
        self._skeleton = QWidget()
        skeleton_layout = QVBoxLayout(self._skeleton)
        skeleton_layout.setContentsMargins(0, 0, 0, 0)
        skeleton_layout.addWidget(SkeletonLoader(100, 20))
        skeleton_layout.addWidget(SkeletonLoader(60, 14))
        self._skeleton.hide()
        layout.addWidget(self._skeleton)

    def _apply_theme(self) -> None:
        tokens = self.tokens

        base_style = f"""
            DeviceCard {{
                background-color: {tokens.surface_card};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
            }}
            DeviceCard:hover {{
                border-color: {tokens.primary};
                background-color: {tokens.interactive_hover};
            }}
        """

        if self._has_error:
            base_style += f"""
                DeviceCard {{
                    border-color: {tokens.error};
                }}
            """

        self.setStyleSheet(base_style)

        self._name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_base};
            font-weight: {tokens.font_weight_semibold};
            color: {tokens.text_primary};
        """
        )

        self._status_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            color: {tokens.text_muted};
        """
        )

    def set_device(self, device_id: str, name: str, status: str, status_color: str, icon_pixmap=None) -> None:
        """Set device information with animation."""
        self._device_id = device_id
        self._name_label.setText(name)
        self._status_label.setText(status)

        # Animate status dot color change
        self._status_dot.set_color(status_color)

        if icon_pixmap and not icon_pixmap.isNull():
            self._icon_label.setPixmap(icon_pixmap)

        # Show content if was loading
        if self._is_loading:
            self.set_loading(False)

    def set_loading(self, loading: bool) -> None:
        """Toggle loading state."""
        self._is_loading = loading

        if loading:
            self._name_label.hide()
            self._status_label.hide()
            self._skeleton.show()
        else:
            self._skeleton.hide()
            self._name_label.show()
            self._status_label.show()

    def set_error(self, has_error: bool) -> None:
        """Toggle error state."""
        self._has_error = has_error
        self._apply_theme()

        if has_error and hasattr(self, "shake"):
            self.shake()

    def enterEvent(self, event) -> None:
        if hasattr(self, "_shadow"):
            self._shadow.setBlurRadius(15)
            self._shadow.setOffset(0, 4)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        if hasattr(self, "_shadow"):
            self._shadow.setBlurRadius(0)
            self._shadow.setOffset(0, 0)
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self._device_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self._device_id)
        super().mouseDoubleClickEvent(event)


class StatusDot(QFrame):
    """
    Animated status indicator dot.

    Features:
    - Smooth color transitions
    - Pulse animation for active status
    """

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._color = "#888888"
        self._is_pulsing = False

        self.setFixedSize(10, 10)

        # Pulse animation
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._pulse_step)
        self._pulse_opacity = 1.0
        self._pulse_direction = -1

    def set_color(self, color: str, pulse: bool = False) -> None:
        """Set dot color with optional pulse."""
        self._color = color
        self._update_style()

        if pulse and not self._is_pulsing:
            self._is_pulsing = True
            self._pulse_timer.start(50)
        elif not pulse and self._is_pulsing:
            self._is_pulsing = False
            self._pulse_timer.stop()
            self._pulse_opacity = 1.0
            self._update_style()

    def _pulse_step(self) -> None:
        """Animation step for pulse."""
        self._pulse_opacity += self._pulse_direction * 0.05

        if self._pulse_opacity <= 0.4:
            self._pulse_direction = 1
        elif self._pulse_opacity >= 1.0:
            self._pulse_direction = -1

        self._update_style()

    def _update_style(self) -> None:
        """Update stylesheet."""
        color = QColor(self._color)
        color.setAlphaF(self._pulse_opacity)

        self.setStyleSheet(
            f"""
            StatusDot {{
                background-color: {color.name(QColor.NameFormat.HexArgb)};
                border-radius: 5px;
                border: 1px solid rgba(255, 255, 255, 0.3);
            }}
        """
        )


class InfoCard(ThemedFrame):
    """
    Information card with icon, title, and description.

    Useful for tips, warnings, or contextual information.
    """

    def __init__(
        self,
        title: str,
        description: str,
        theme_service: "ThemeService",
        variant: str = "info",  # info, warning, error, success
        parent: Optional[QWidget] = None,
    ):
        super().__init__(theme_service, parent)
        self._title = title
        self._description = description
        self._variant = variant

        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(10)

        # Icon
        self._icon = QLabel()
        self._icon.setFixedSize(24, 24)
        icons = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "success": "✅",
        }
        self._icon.setText(icons.get(self._variant, "ℹ️"))
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        # Content
        content = QVBoxLayout()
        content.setSpacing(2)

        self._title_label = QLabel(self._title)
        content.addWidget(self._title_label)

        self._desc_label = QLabel(self._description)
        self._desc_label.setWordWrap(True)
        content.addWidget(self._desc_label)

        layout.addLayout(content, 1)

    def _apply_theme(self) -> None:
        tokens = self.tokens

        colors = {
            "info": (tokens.info, tokens.info + "20"),
            "warning": (tokens.warning, tokens.warning + "20"),
            "error": (tokens.error, tokens.error + "20"),
            "success": (tokens.success, tokens.success + "20"),
        }

        accent, bg = colors.get(self._variant, (tokens.info, tokens.info + "20"))

        self.setStyleSheet(
            f"""
            InfoCard {{
                background: {bg};
                border: 1px solid {accent};
                border-radius: {tokens.radius_md};
            }}
        """
        )

        self._title_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_sm};
            font-weight: {tokens.font_weight_semibold};
            color: {accent};
        """
        )

        self._desc_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_secondary};
        """
        )


__all__ = [
    "Card",
    "ElevatedCard",
    "StatCard",
    "DeviceCard",
    "StatusDot",
    "InfoCard",
]
