# File: presentation/views/components/progress.py
"""
Progress bar components with animation support.

Usage:
    bar = AnimatedProgressBar("#10B981", theme_service)
    bar.animate_to(75.0)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from PySide6.QtCore import Property, QEasingCurve, QPropertyAnimation
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService


class AnimatedProgressBar(QWidget):
    """
    Animated progress bar with smooth transitions.

    Usage:
        bar = AnimatedProgressBar("#10B981", theme_service)
        bar.animate_to(75.0)
    """

    def __init__(self, color: str, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._color = QColor(color)
        self._value = 0.0
        self._animation: Optional[QPropertyAnimation] = None

        self.setFixedHeight(4)
        self.setMinimumWidth(60)

        self._theme_service.themeChanged.connect(self._on_theme_changed)

    def _on_theme_changed(self, theme: str) -> None:
        self.update()

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, value))
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, target: float, duration: int = 500) -> None:
        """Animate to target value."""
        target = max(0.0, min(100.0, target))

        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(duration)
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(target)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()

    def set_color(self, color: str) -> None:
        """Change the progress bar color."""
        self._color = QColor(color)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        tokens = self._theme_service.tokens

        # Track background
        track_color = QColor(tokens.interactive_hover)
        painter.setBrush(QBrush(track_color))
        painter.setPen(QPen(Qt.PenStyle.NoPen))
        painter.drawRoundedRect(rect, 2, 2)

        # Progress fill
        if self._value > 0:
            fill_width = rect.width() * (self._value / 100.0)
            fill_rect = rect.adjusted(0, 0, int(fill_width - rect.width()), 0)

            gradient = QLinearGradient(fill_rect.topLeft(), fill_rect.topRight())
            gradient.setColorAt(0, self._color.lighter(110))
            gradient.setColorAt(1, self._color)

            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(fill_rect, 2, 2)


class StatusProgressBar(AnimatedProgressBar):
    """
    Progress bar that changes color based on value thresholds.

    - 0-50: error (red)
    - 50-80: warning (yellow)
    - 80-100: success (green)
    """

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__("#10B981", theme_service, parent)
        self._update_color()

    def set_value(self, value: float) -> None:
        super().set_value(value)
        self._update_color()

    def _update_color(self) -> None:
        tokens = self._theme_service.tokens

        if self._value < 50:
            self._color = QColor(tokens.error)
        elif self._value < 80:
            self._color = QColor(tokens.warning)
        else:
            self._color = QColor(tokens.success)

        self.update()

    def animate_to(self, target: float, duration: int = 500) -> None:
        # Update color based on target
        tokens = self._theme_service.tokens

        if target < 50:
            self._color = QColor(tokens.error)
        elif target < 80:
            self._color = QColor(tokens.warning)
        else:
            self._color = QColor(tokens.success)

        super().animate_to(target, duration)


class CircularProgress(QWidget):
    """
    Circular progress indicator.

    Usage:
        progress = CircularProgress(theme_service, size=64)
        progress.set_value(75)
    """

    def __init__(self, theme_service: "ThemeService", size: int = 48, thickness: int = 4, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._size = size
        self._thickness = thickness
        self._value = 0.0
        self._animation: Optional[QPropertyAnimation] = None

        self.setFixedSize(size, size)
        self._theme_service.themeChanged.connect(lambda _: self.update())

    def get_value(self) -> float:
        return self._value

    def set_value(self, value: float) -> None:
        self._value = max(0.0, min(100.0, value))
        self.update()

    value = Property(float, get_value, set_value)

    def animate_to(self, target: float, duration: int = 500) -> None:
        target = max(0.0, min(100.0, target))

        if self._animation:
            self._animation.stop()

        self._animation = QPropertyAnimation(self, b"value")
        self._animation.setDuration(duration)
        self._animation.setStartValue(self._value)
        self._animation.setEndValue(target)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._animation.start()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tokens = self._theme_service.tokens

        # Calculate dimensions
        margin = self._thickness / 2
        rect = self.rect().adjusted(int(margin), int(margin), int(-margin), int(-margin))

        # Track
        track_pen = QPen(QColor(tokens.interactive_hover), self._thickness)
        track_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(track_pen)
        painter.drawArc(rect, 0, 360 * 16)

        # Progress
        if self._value > 0:
            progress_pen = QPen(QColor(tokens.primary), self._thickness)
            progress_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(progress_pen)

            span = int((self._value / 100.0) * 360 * 16)
            painter.drawArc(rect, 90 * 16, -span)  # Start from top

        # Center text
        painter.setPen(QColor(tokens.text_primary))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, f"{int(self._value)}%")


__all__ = [
    "AnimatedProgressBar",
    "StatusProgressBar",
    "CircularProgress",
]
