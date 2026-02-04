# presentation/views/components/toast.py
"""
Toast Notification Components.

Features:
- Slide-in/out animations
- Auto-dismiss with progress
- Action buttons
- Stacking support
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Dict, Optional, Callable

from PySide6.QtCore import Qt, Signal, QTimer, QPropertyAnimation, QEasingCurve, Property, QPoint
from PySide6.QtWidgets import QWidget, QFrame, QLabel, QPushButton, QHBoxLayout, QVBoxLayout, QGraphicsOpacityEffect, QProgressBar, QSizePolicy
from PySide6.QtGui import QFont

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...state.store import Toast, ToastManager


class ToastWidget(QFrame):
    """
    Individual toast notification widget.

    Features:
    - Icon based on variant
    - Progress bar countdown
    - Dismiss button
    - Hover to pause
    """

    dismissed = Signal(str)  # toast_id
    action_clicked = Signal(str, str)  # toast_id, action_callback

    ICONS = {
        "info": "ℹ️",
        "success": "✓",
        "warning": "⚠",
        "error": "✕",
    }

    def __init__(
        self,
        toast_id: str,
        message: str,
        variant: str = "info",
        duration: int = 3000,
        action_label: Optional[str] = None,
        action_callback: Optional[str] = None,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._toast_id = toast_id
        self._message = message
        self._variant = variant
        self._duration = duration
        self._action_label = action_label
        self._action_callback = action_callback
        self._theme_service = theme_service

        self._opacity_effect: Optional[QGraphicsOpacityEffect] = None
        self._progress_timer: Optional[QTimer] = None
        self._elapsed_ms = 0
        self._is_hovered = False

        self.setObjectName("toast_widget")
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setFixedHeight(64)
        self.setMinimumWidth(280)
        self.setMaximumWidth(400)

        self._setup_ui()
        self._apply_style()
        self._setup_animations()

        if duration > 0:
            self._start_countdown()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(12)

        # Icon
        self._icon_label = QLabel(self.ICONS.get(self._variant, "ℹ️"))
        self._icon_label.setFixedSize(28, 28)
        self._icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = QFont()
        font.setPointSize(16)
        self._icon_label.setFont(font)
        layout.addWidget(self._icon_label)

        # Content
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(4)

        self._message_label = QLabel(self._message)
        self._message_label.setWordWrap(True)
        self._message_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        content_layout.addWidget(self._message_label)

        # Progress bar
        if self._duration > 0:
            self._progress_bar = QProgressBar()
            self._progress_bar.setFixedHeight(3)
            self._progress_bar.setTextVisible(False)
            self._progress_bar.setRange(0, 100)
            self._progress_bar.setValue(100)
            content_layout.addWidget(self._progress_bar)

        layout.addLayout(content_layout, 1)

        # Action button
        if self._action_label:
            self._action_btn = QPushButton(self._action_label)
            self._action_btn.setObjectName("toast_action_btn")
            self._action_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            self._action_btn.clicked.connect(self._on_action_clicked)
            layout.addWidget(self._action_btn)

        # Dismiss button
        self._dismiss_btn = QPushButton("×")
        self._dismiss_btn.setObjectName("toast_dismiss_btn")
        self._dismiss_btn.setFixedSize(24, 24)
        self._dismiss_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._dismiss_btn.clicked.connect(self._on_dismiss_clicked)
        layout.addWidget(self._dismiss_btn)

    def _apply_style(self) -> None:
        if not self._theme_service:
            self._apply_fallback_style()
            return

        tokens = self._theme_service.tokens

        # Variant colors
        variant_styles = {
            "info": (tokens.primary, tokens.primary_subtle),
            "success": (tokens.success, tokens.success_subtle),
            "warning": (tokens.warning, tokens.warning_subtle),
            "error": (tokens.error, tokens.error_subtle),
        }

        accent, bg = variant_styles.get(self._variant, (tokens.primary, tokens.surface_card))

        self.setStyleSheet(
            f"""
            QFrame#toast_widget {{
                background: {bg};
                border: 1px solid {accent};
                border-left: 4px solid {accent};
                border-radius: {tokens.radius_md};
            }}
            
            QLabel {{
                color: {tokens.text_primary};
                font-size: {tokens.font_size_sm};
                background: transparent;
            }}
            
            QPushButton#toast_action_btn {{
                background: {accent};
                color: white;
                border: none;
                border-radius: {tokens.radius_sm};
                padding: 6px 14px;
                font-weight: 600;
                font-size: {tokens.font_size_xs};
            }}
            
            QPushButton#toast_action_btn:hover {{
                opacity: 0.9;
            }}
            
            QPushButton#toast_dismiss_btn {{
                background: transparent;
                border: none;
                color: {tokens.text_muted};
                font-size: 18px;
                font-weight: bold;
            }}
            
            QPushButton#toast_dismiss_btn:hover {{
                color: {tokens.text_primary};
            }}
            
            QProgressBar {{
                background: {tokens.border_default};
                border: none;
                border-radius: 1px;
            }}
            
            QProgressBar::chunk {{
                background: {accent};
                border-radius: 1px;
            }}
        """
        )

    def _apply_fallback_style(self) -> None:
        """Fallback style without theme service."""
        variant_colors = {
            "info": ("#3B82F6", "#EFF6FF"),
            "success": ("#10B981", "#ECFDF5"),
            "warning": ("#F59E0B", "#FFFBEB"),
            "error": ("#EF4444", "#FEF2F2"),
        }

        accent, bg = variant_colors.get(self._variant, ("#3B82F6", "#FFFFFF"))

        self.setStyleSheet(
            f"""
            QFrame#toast_widget {{
                background: {bg};
                border: 1px solid {accent};
                border-left: 4px solid {accent};
                border-radius: 8px;
            }}
            QLabel {{ color: #1F2937; font-size: 13px; background: transparent; }}
            QPushButton#toast_dismiss_btn {{
                background: transparent; border: none;
                color: #9CA3AF; font-size: 18px;
            }}
            QProgressBar {{ background: #E5E7EB; border: none; }}
            QProgressBar::chunk {{ background: {accent}; }}
        """
        )

    def _setup_animations(self) -> None:
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(0)
        self.setGraphicsEffect(self._opacity_effect)

    def _start_countdown(self) -> None:
        self._progress_timer = QTimer(self)
        self._progress_timer.timeout.connect(self._update_progress)
        self._progress_timer.start(50)

    def _update_progress(self) -> None:
        if self._is_hovered:
            return

        self._elapsed_ms += 50

        if self._elapsed_ms >= self._duration:
            self._progress_timer.stop()
            self.dismiss(animate=True)
            return

        progress = 100 - int((self._elapsed_ms / self._duration) * 100)
        if hasattr(self, "_progress_bar"):
            self._progress_bar.setValue(progress)

    def show_animated(self) -> None:
        self.show()

        anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        anim.setDuration(200)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        anim.start()

        # Store reference to prevent GC
        self._show_anim = anim

    def dismiss(self, animate: bool = True) -> None:
        if self._progress_timer:
            self._progress_timer.stop()

        if animate and self._opacity_effect:
            anim = QPropertyAnimation(self._opacity_effect, b"opacity")
            anim.setDuration(200)
            anim.setStartValue(1.0)
            anim.setEndValue(0.0)
            anim.setEasingCurve(QEasingCurve.Type.InCubic)
            anim.finished.connect(self._emit_dismissed)
            anim.start()
            self._dismiss_anim = anim
        else:
            self._emit_dismissed()

    def _emit_dismissed(self) -> None:
        self.dismissed.emit(self._toast_id)
        self.close()

    def _on_action_clicked(self) -> None:
        if self._action_callback:
            self.action_clicked.emit(self._toast_id, self._action_callback)
        self.dismiss(animate=True)

    def _on_dismiss_clicked(self) -> None:
        self.dismiss(animate=True)

    def enterEvent(self, event) -> None:
        self._is_hovered = True
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._is_hovered = False
        super().leaveEvent(event)


class ToastContainer(QWidget):
    """
    Container for stacking multiple toasts.

    Features:
    - Positioning (top-right default)
    - Stacking with animations
    - Max visible limit
    """

    POSITIONS = {
        "top-right": (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight),
        "top-left": (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft),
        "bottom-right": (Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight),
        "bottom-left": (Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignLeft),
        "top-center": (Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter),
        "bottom-center": (Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignHCenter),
    }

    def __init__(
        self,
        toast_manager: Optional["ToastManager"] = None,
        theme_service: Optional["ThemeService"] = None,
        position: str = "top-right",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._toast_manager = toast_manager
        self._theme_service = theme_service
        self._position = position
        self._toast_widgets: Dict[str, ToastWidget] = {}

        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self._setup_ui()

        if toast_manager:
            self._connect_signals()

    def _setup_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(8)
        self._layout.setAlignment(self.POSITIONS.get(self._position, Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight))

    def _connect_signals(self) -> None:
        if self._toast_manager:
            self._toast_manager.toast_added.connect(self._on_toast_added)
            self._toast_manager.toast_removed.connect(self._on_toast_removed)

    def _on_toast_added(self, toast: "Toast") -> None:
        widget = ToastWidget(
            toast_id=toast.id,
            message=toast.message,
            variant=toast.variant,
            duration=toast.duration,
            action_label=toast.action_label,
            action_callback=toast.action_callback,
            theme_service=self._theme_service,
            parent=self,
        )

        widget.dismissed.connect(self._on_widget_dismissed)

        self._toast_widgets[toast.id] = widget
        self._layout.addWidget(widget)

        widget.show_animated()
        self._update_geometry()

    def _on_toast_removed(self, toast_id: str) -> None:
        if toast_id in self._toast_widgets:
            widget = self._toast_widgets.pop(toast_id)
            widget.deleteLater()
            self._update_geometry()

    def _on_widget_dismissed(self, toast_id: str) -> None:
        if self._toast_manager:
            self._toast_manager.dismiss(toast_id, animate=False)
        elif toast_id in self._toast_widgets:
            self._toast_widgets.pop(toast_id, None)

    def _update_geometry(self) -> None:
        if not self.parent():
            return

        # Adjust size to content
        self.adjustSize()

        parent_rect = self.parent().rect()
        margin = 16

        # Calculate position
        if "right" in self._position:
            x = parent_rect.right() - self.width() - margin
        elif "left" in self._position:
            x = margin
        else:
            x = (parent_rect.width() - self.width()) // 2

        if "top" in self._position:
            y = margin + 52  # Account for header
        else:
            y = parent_rect.bottom() - self.height() - margin - 32  # Account for status bar

        self.move(x, y)
        self.show()
        self.raise_()

    # =========================================================================
    # Manual toast creation (without ToastManager)
    # =========================================================================

    def show_toast(
        self,
        message: str,
        variant: str = "info",
        duration: int = 3000,
    ) -> str:
        """Show toast without ToastManager."""
        toast_id = str(uuid.uuid4())[:8]

        widget = ToastWidget(
            toast_id=toast_id,
            message=message,
            variant=variant,
            duration=duration,
            theme_service=self._theme_service,
            parent=self,
        )

        widget.dismissed.connect(self._on_widget_dismissed)

        self._toast_widgets[toast_id] = widget
        self._layout.addWidget(widget)

        widget.show_animated()
        self._update_geometry()

        return toast_id

    def success(self, message: str, duration: int = 3000) -> str:
        return self.show_toast(message, "success", duration)

    def error(self, message: str, duration: int = 5000) -> str:
        return self.show_toast(message, "error", duration)

    def warning(self, message: str, duration: int = 4000) -> str:
        return self.show_toast(message, "warning", duration)

    def info(self, message: str, duration: int = 3000) -> str:
        return self.show_toast(message, "info", duration)


__all__ = ["ToastWidget", "ToastContainer"]
