"""
Professional UX State Widgets - Loading, Empty, Error States.

Provides polished, professional-looking UI states for:
- Loading states with progress indication
- Empty states with helpful messages and actions
- Error states with clear information and recovery options

Design Goals:
- Consistent visual language across app
- Clear communication to users
- Actionable states (not just informational)
- Smooth transitions and animations
"""

from __future__ import annotations
import logging
from typing import Optional

from PySide6.QtCore import Qt, QPropertyAnimation, QEasingCurve, QTimer, Signal
from PySide6.QtGui import QFont, QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
    QFrame,
)

logger = logging.getLogger(__name__)


class LoadingStateWidget(QWidget):
    """
    Professional loading state widget.

    Features:
    - Animated spinner
    - Progress bar for long operations
    - Cancelable operations
    - Smooth fade in/out animations
    """

    cancelled = Signal()

    def __init__(
        self,
        message: str = "Loading...",
        show_cancel: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._show_cancel = show_cancel
        self._setup_ui()
        self._setup_animations()
        self.hide()

    def _setup_ui(self) -> None:
        """Setup loading state UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._spinner = QLabel()
        self._spinner.setFixedSize(64, 64)
        self._spinner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spinner.setStyleSheet(
            """
            QLabel {
                background-color: transparent;
                border: 3px solid #0078D4;
                border-radius: 32px;
                border-top-color: transparent;
            }
        """
        )
        self._spinner.hide()

        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.setTextVisible(False)
        self._progress_bar.setMaximumHeight(4)
        self._progress_bar.setStyleSheet(
            """
            QProgressBar {
                border: none;
                background-color: rgba(0, 120, 212, 0.1);
                border-radius: 2px;
            }
            QProgressBar::chunk {
                background-color: #0078D4;
                border-radius: 2px;
            }
        """
        )

        self._message_label = QLabel(self._message)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: palette(text);
                background: transparent;
            }
        """
        )

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self._cancel_button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: 1px solid palette(mid);
                border-radius: 4px;
                padding: 6px 16px;
                color: palette(text);
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: palette(alternate-base);
                border-color: #0078D4;
            }
            QPushButton:pressed {
                background-color: rgba(0, 120, 212, 0.1);
            }
        """
        )
        self._cancel_button.clicked.connect(self.cancelled.emit)

        layout.addStretch()
        layout.addWidget(self._spinner, 0, Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._progress_bar)
        layout.addWidget(self._message_label)
        if self._show_cancel:
            cancel_layout = QHBoxLayout()
            cancel_layout.addStretch()
            cancel_layout.addWidget(self._cancel_button)
            cancel_layout.addStretch()
            layout.addLayout(cancel_layout)
        layout.addStretch()

    def _setup_animations(self) -> None:
        """Setup rotation animation for spinner."""
        self._rotation_angle = 0
        self._rotation_timer = QTimer(self)
        self._rotation_timer.timeout.connect(self._rotate_spinner)
        self._rotation_timer.start(16)

        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(200)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _rotate_spinner(self) -> None:
        """Rotate spinner for animation effect."""
        self._rotation_angle = (self._rotation_angle + 10) % 360
        if self._spinner.isVisible():
            self._spinner.setTransformOriginPoint(32, 32)
            self._spinner.setRotation(self._rotation_angle)

    def set_message(self, message: str) -> None:
        """Update loading message."""
        self._message = message
        self._message_label.setText(message)

    def set_progress(self, value: int, maximum: int = 100) -> None:
        """Set progress bar value."""
        self._progress_bar.setRange(0, maximum)
        self._progress_bar.setValue(value)

    def set_indeterminate(self) -> None:
        """Set indeterminate progress."""
        self._progress_bar.setRange(0, 0)

    def show_event(self, event) -> None:
        """Handle show event."""
        super().showEvent(event)
        self._spinner.show()
        self._fade_animation.setStartValue(0.0)
        self._fade_animation.setEndValue(1.0)
        self._fade_animation.start()

    def hide_event(self, event) -> None:
        """Handle hide event."""
        super().hideEvent(event)
        self._spinner.hide()


class EmptyStateWidget(QWidget):
    """
    Professional empty state widget.

    Features:
    - Clear, helpful messaging
    - Illustration or icon
    - Action buttons (optional)
    - Context-specific suggestions
    """

    action_triggered = Signal(str)

    def __init__(
        self,
        message: str = "No data available",
        illustration: str = "",
        actions: Optional[list[tuple[str, str]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._message = message
        self._illustration = illustration
        self._actions = actions or []
        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        """Setup empty state UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        if self._illustration:
            self._illustration_label = QLabel()
            self._illustration_label.setPixmap(QPixmap(self._illustration))
            self._illustration_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._illustration_label.setStyleSheet("background: transparent;")
            layout.addWidget(self._illustration_label, 0, Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("📭")
        icon_label.setStyleSheet(
            """
            QLabel {
                font-size: 64px;
                background: transparent;
            }
        """
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        self._message_label = QLabel(self._message)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(
            """
            QLabel {
                font-size: 16px;
                color: palette(text);
                background: transparent;
                padding: 0 16px;
            }
        """
        )
        layout.addWidget(self._message_label)

        self._setup_actions(layout)

        layout.addStretch()

    def _setup_actions(self, parent_layout: QVBoxLayout) -> None:
        """Setup action buttons."""
        if not self._actions:
            return

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for action_id, action_text in self._actions:
            button = QPushButton(action_text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #0078D4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #106EBE;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
            """
            )
            button.clicked.connect(lambda _, aid=action_id: self.action_triggered.emit(aid))
            actions_layout.addWidget(button)

        parent_layout.addLayout(actions_layout)

    def set_message(self, message: str) -> None:
        """Update empty state message."""
        self._message = message
        self._message_label.setText(message)


class ErrorStateWidget(QWidget):
    """
    Professional error state widget.

    Features:
    - Clear error message
    - Error details (expandable)
    - Recovery actions
    - Support link/contact option
    """

    action_triggered = Signal(str)

    def __init__(
        self,
        title: str = "Error",
        message: str = "An error occurred",
        details: Optional[str] = None,
        actions: Optional[list[tuple[str, str]]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._message = message
        self._details = details
        self._actions = actions or []
        self._setup_ui()
        self.hide()

    def _setup_ui(self) -> None:
        """Setup error state UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel("⚠️")
        icon_label.setStyleSheet(
            """
            QLabel {
                font-size: 64px;
                background: transparent;
            }
        """
        )
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label, 0, Qt.AlignmentFlag.AlignCenter)

        self._title_label = QLabel(self._title)
        self._title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._title_label.setStyleSheet(
            """
            QLabel {
                font-size: 18px;
                font-weight: 600;
                color: palette(text);
                background: transparent;
            }
        """
        )
        layout.addWidget(self._title_label)

        self._message_label = QLabel(self._message)
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        self._message_label.setStyleSheet(
            """
            QLabel {
                font-size: 14px;
                color: palette(text);
                background: transparent;
                padding: 0 16px;
            }
        """
        )
        layout.addWidget(self._message_label)

        if self._details:
            self._details_label = QLabel(self._details)
            self._details_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self._details_label.setWordWrap(True)
            self._details_label.setStyleSheet(
                """
                QLabel {
                    font-size: 12px;
                    color: palette(mid);
                    background: transparent;
                    padding: 0 16px;
                    font-family: monospace;
                }
            """
            )
            layout.addWidget(self._details_label)

        self._setup_actions(layout)
        layout.addStretch()

    def _setup_actions(self, parent_layout: QVBoxLayout) -> None:
        """Setup action buttons."""
        if not self._actions:
            return

        actions_layout = QHBoxLayout()
        actions_layout.setSpacing(8)
        actions_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        for action_id, action_text in self._actions:
            button = QPushButton(action_text)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            is_primary = action_id == "retry"
            button.setStyleSheet(
                """
                QPushButton {
                    background-color: #0078D4;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-size: 13px;
                    font-weight: 500;
                }
                QPushButton:hover {
                    background-color: #106EBE;
                }
                QPushButton:pressed {
                    background-color: #005A9E;
                }
                """
                if is_primary
                else """
                QPushButton {
                    background-color: transparent;
                    color: palette(text);
                    border: 1px solid palette(mid);
                    border-radius: 4px;
                    padding: 8px 20px;
                    font-size: 13px;
                }
                QPushButton:hover {
                    background-color: palette(alternate-base);
                    border-color: #0078D4;
                }
            """
            )
            button.clicked.connect(lambda _, aid=action_id: self.action_triggered.emit(aid))
            actions_layout.addWidget(button)

        parent_layout.addLayout(actions_layout)


__all__ = ["LoadingStateWidget", "EmptyStateWidget", "ErrorStateWidget"]
