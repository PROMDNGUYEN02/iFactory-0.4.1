# presentation/views/components/error_boundary.py
"""
Error Boundary - Graceful error handling for UI components.

Features:
- Catch rendering errors
- Display fallback UI
- Error reporting
- Recovery actions
"""

from __future__ import annotations

import logging
import traceback
from typing import Optional, Callable, TYPE_CHECKING
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QTextEdit, QSizePolicy
from PySide6.QtGui import QFont

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService

logger = logging.getLogger(__name__)


class ErrorBoundary(QFrame):
    """
    Error boundary wrapper for child widgets.

    Usage:
        boundary = ErrorBoundary(theme_service=theme_service)
        boundary.set_child(MyRiskyWidget())
    """

    error_occurred = Signal(Exception, str)  # exception, traceback
    recovery_attempted = Signal()

    def __init__(
        self,
        fallback_message: str = "Something went wrong",
        show_details: bool = True,
        on_retry: Optional[Callable[[], None]] = None,
        theme_service: Optional["ThemeService"] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        self._fallback_message = fallback_message
        self._show_details = show_details
        self._on_retry = on_retry
        self._theme_service = theme_service

        self._child: Optional[QWidget] = None
        self._error: Optional[Exception] = None
        self._traceback: str = ""
        self._has_error = False

        self._setup_ui()

    def _setup_ui(self) -> None:
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)

        # Error view (hidden initially)
        self._error_view = self._create_error_view()
        self._error_view.hide()
        self._layout.addWidget(self._error_view)

    def _create_error_view(self) -> QWidget:
        """Create error fallback UI."""
        container = QFrame()
        container.setObjectName("error_boundary_fallback")

        layout = QVBoxLayout(container)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # Icon
        icon = QLabel("⚠️")
        icon.setFont(QFont("Segoe UI Emoji", 32))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # Message
        self._message_label = QLabel(self._fallback_message)
        self._message_label.setObjectName("error_message")
        self._message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message_label.setWordWrap(True)
        layout.addWidget(self._message_label)

        # Error details (collapsible)
        if self._show_details:
            self._details_toggle = QPushButton("Show Details")
            self._details_toggle.setObjectName("details_toggle")
            self._details_toggle.clicked.connect(self._toggle_details)
            layout.addWidget(self._details_toggle, alignment=Qt.AlignmentFlag.AlignCenter)

            self._details_text = QTextEdit()
            self._details_text.setReadOnly(True)
            self._details_text.setMaximumHeight(150)
            self._details_text.hide()
            layout.addWidget(self._details_text)

        # Actions
        actions = QHBoxLayout()
        actions.setSpacing(12)

        if self._on_retry:
            retry_btn = QPushButton("🔄 Retry")
            retry_btn.setObjectName("retry_button")
            retry_btn.clicked.connect(self._retry)
            actions.addWidget(retry_btn)

        copy_btn = QPushButton("📋 Copy Error")
        copy_btn.setObjectName("copy_button")
        copy_btn.clicked.connect(self._copy_error)
        actions.addWidget(copy_btn)

        layout.addLayout(actions)

        self._apply_error_style(container)

        return container

    def _apply_error_style(self, container: QFrame) -> None:
        """Apply styling to error view."""
        if self._theme_service:
            tokens = self._theme_service.tokens
            container.setStyleSheet(
                f"""
                QFrame#error_boundary_fallback {{
                    background: {tokens.surface_card};
                    border: 1px solid {tokens.error};
                    border-radius: {tokens.radius_lg};
                }}
                
                QLabel#error_message {{
                    color: {tokens.text_primary};
                    font-size: 16px;
                    font-weight: 500;
                }}
                
                QPushButton {{
                    background: {tokens.surface_elevated};
                    border: 1px solid {tokens.border_default};
                    border-radius: {tokens.radius_sm};
                    padding: 8px 16px;
                    color: {tokens.text_primary};
                }}
                
                QPushButton:hover {{
                    background: {tokens.interactive_hover};
                }}
                
                QPushButton#retry_button {{
                    background: {tokens.primary};
                    color: white;
                    border: none;
                }}
                
                QTextEdit {{
                    background: {tokens.surface_elevated};
                    border: 1px solid {tokens.border_default};
                    border-radius: {tokens.radius_sm};
                    color: {tokens.text_secondary};
                    font-family: monospace;
                    font-size: 11px;
                }}
            """
            )
        else:
            container.setStyleSheet(
                """
                QFrame#error_boundary_fallback {
                    background: #FFF5F5;
                    border: 1px solid #F56565;
                    border-radius: 8px;
                }
                QLabel#error_message {
                    color: #1A202C;
                    font-size: 16px;
                }
            """
            )

    def set_child(self, widget: QWidget) -> None:
        """Set the child widget to wrap."""
        # Remove existing child
        if self._child:
            self._layout.removeWidget(self._child)
            self._child.deleteLater()

        self._child = widget
        self._layout.insertWidget(0, widget)
        self._has_error = False
        self._error_view.hide()
        widget.show()

    def catch_error(self, error: Exception) -> None:
        """Handle caught error."""
        self._error = error
        self._traceback = traceback.format_exc()
        self._has_error = True

        logger.error(f"[ErrorBoundary] Caught error: {error}")
        logger.debug(self._traceback)

        # Hide child, show error
        if self._child:
            self._child.hide()

        self._message_label.setText(f"{self._fallback_message}\n\n{str(error)}")

        if self._show_details:
            self._details_text.setPlainText(self._traceback)

        self._error_view.show()

        self.error_occurred.emit(error, self._traceback)

    def _toggle_details(self) -> None:
        """Toggle error details visibility."""
        if self._details_text.isVisible():
            self._details_text.hide()
            self._details_toggle.setText("Show Details")
        else:
            self._details_text.show()
            self._details_toggle.setText("Hide Details")

    def _retry(self) -> None:
        """Attempt recovery."""
        self._error_view.hide()

        if self._child:
            self._child.show()

        self._has_error = False
        self.recovery_attempted.emit()

        if self._on_retry:
            try:
                self._on_retry()
            except Exception as e:
                self.catch_error(e)

    def _copy_error(self) -> None:
        """Copy error to clipboard."""
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        error_text = f"Error: {self._error}\n\n{self._traceback}"
        clipboard.setText(error_text)

        # Show feedback
        if self._theme_service and hasattr(self._theme_service, "store"):
            self._theme_service.store.show_toast("Error copied to clipboard", "info")


def with_error_boundary(
    widget_class: type,
    fallback_message: str = "Component failed to load",
    theme_service: Optional["ThemeService"] = None,
    **widget_kwargs,
) -> ErrorBoundary:
    """
    Factory function to wrap a widget with error boundary.

    Usage:
        widget = with_error_boundary(MyWidget, theme_service=ts, arg1=val1)
    """
    boundary = ErrorBoundary(
        fallback_message=fallback_message,
        theme_service=theme_service,
    )

    try:
        child = widget_class(**widget_kwargs)
        boundary.set_child(child)
    except Exception as e:
        boundary.catch_error(e)

    return boundary


__all__ = ["ErrorBoundary", "with_error_boundary"]
