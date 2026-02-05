# presentation/views/shell/right_panel.py
"""
Enhanced Right Panel - Device details with Loading/Error/Stale states.

NEW FEATURES:
- Skeleton loading animation
- Error state with retry button
- Stale data banner
- Connection indicator
- Smooth transitions

FIXED:
- QGradient::setColorAt position must be in range 0-1
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Tuple

from PySide6.QtCore import Qt, Slot, QTimer, QPropertyAnimation, QEasingCurve, Property, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QPushButton,
    QStackedWidget,
    QGraphicsOpacityEffect,
    QSizePolicy,
)
from PySide6.QtGui import QFont, QColor, QPainter, QLinearGradient

from ...constants.layout import Layout

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService
    from ...state.store import Store
    from ...viewmodels import DeviceListViewModel, ShellViewModel
    from ...viewmodels.models.device_model import MaterialInputModel, DeviceDisplayModel

logger = logging.getLogger(__name__)


# =============================================================================
# Helper Functions
# =============================================================================


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a value to the specified range [min_val, max_val]."""
    return max(min_val, min(max_val, value))


# =============================================================================
# Constants
# =============================================================================


class PanelState:
    """Panel content states."""

    PLACEHOLDER = 0
    LOADING = 1
    ERROR = 2
    CONTENT = 3


# =============================================================================
# Skeleton Loader Component
# =============================================================================


class SkeletonLine(QWidget):
    """Animated skeleton line with shimmer effect."""

    def __init__(self, width: int = 100, height: int = 14, radius: int = 4, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._radius = radius
        self._shimmer_pos = 0.0

        self.setFixedSize(width, height)

        # Animation timer
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_shimmer)

    def _update_shimmer(self) -> None:
        # FIXED: Keep shimmer_pos in range 0.0 to 1.0
        self._shimmer_pos = (self._shimmer_pos + 0.03) % 1.0
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()

        # Base gradient with shimmer
        gradient = QLinearGradient(0, 0, rect.width(), 0)

        base = QColor("#E2E8F0")
        highlight = QColor("#F8FAFC")

        pos = self._shimmer_pos

        # FIXED: Clamp all gradient positions to valid range [0.0, 1.0]
        # Create shimmer effect that moves across the widget
        shimmer_width = 0.3

        pos_start = clamp(pos - shimmer_width)
        pos_center = clamp(pos)
        pos_end = clamp(pos + shimmer_width)

        gradient.setColorAt(0.0, base)
        if pos_start > 0.0:
            gradient.setColorAt(pos_start, base)
        gradient.setColorAt(pos_center, highlight)
        if pos_end < 1.0:
            gradient.setColorAt(pos_end, base)
        gradient.setColorAt(1.0, base)

        painter.setBrush(gradient)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, self._radius, self._radius)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._timer.start(30)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._timer.stop()


class DeviceDetailSkeleton(QFrame):
    """Skeleton loader for device details panel."""

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self.setObjectName("detail_skeleton")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(16)

        # Header skeleton
        header = QHBoxLayout()
        header.addWidget(SkeletonLine(120, 18, 4))
        header.addStretch()
        header.addWidget(SkeletonLine(60, 24, 12))  # Badge
        layout.addLayout(header)

        # Description
        layout.addWidget(SkeletonLine(200, 12, 4))
        layout.addWidget(SkeletonLine(150, 12, 4))

        # Separator
        layout.addSpacing(8)

        # Section header
        layout.addWidget(SkeletonLine(100, 14, 4))

        # Material items
        for _ in range(2):
            item = QFrame()
            item.setFixedHeight(60)
            item_layout = QVBoxLayout(item)
            item_layout.setContentsMargins(8, 8, 8, 8)
            item_layout.addWidget(SkeletonLine(140, 12, 4))
            item_layout.addWidget(SkeletonLine(100, 10, 4))
            item_layout.addWidget(SkeletonLine(80, 10, 4))
            layout.addWidget(item)

        layout.addSpacing(8)

        # Metrics
        for _ in range(3):
            metric = QHBoxLayout()
            metric.addWidget(SkeletonLine(80, 14, 4))
            metric.addStretch()
            metric.addWidget(SkeletonLine(50, 14, 4))
            layout.addLayout(metric)

            # Progress bar
            layout.addWidget(SkeletonLine(250, 8, 4))

        layout.addStretch()

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens
        self.setStyleSheet(
            f"""
            QFrame#detail_skeleton {{
                background: transparent;
            }}
        """
        )


# =============================================================================
# Error State Component
# =============================================================================


class ErrorStateWidget(QFrame):
    """Error state with retry button."""

    retry_clicked = Signal()

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._error_message = ""
        self._retry_count = 0
        self._max_retries = 3

        self.setObjectName("error_state")
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 40, 24, 40)

        # Icon
        self._icon = QLabel("⚠️")
        self._icon.setFont(QFont("Segoe UI Emoji", 36))
        self._icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._icon)

        # Title
        self._title = QLabel("Failed to load device data")
        self._title.setObjectName("error_title")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._title)

        # Message
        self._message = QLabel("")
        self._message.setObjectName("error_message")
        self._message.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._message.setWordWrap(True)
        layout.addWidget(self._message)

        # Retry button
        self._retry_btn = QPushButton("🔄 Retry")
        self._retry_btn.setObjectName("retry_button")
        self._retry_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._retry_btn.setFixedWidth(120)
        self._retry_btn.clicked.connect(self._on_retry)
        layout.addWidget(self._retry_btn, alignment=Qt.AlignmentFlag.AlignCenter)

        # Retry count label
        self._retry_label = QLabel("")
        self._retry_label.setObjectName("retry_label")
        self._retry_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._retry_label)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            QFrame#error_state {{
                background: {tokens.error_subtle};
                border: 1px solid {tokens.error};
                border-radius: {tokens.radius_lg};
                margin: 16px;
            }}
            
            QLabel#error_title {{
                color: {tokens.error};
                font-size: {tokens.font_size_lg};
                font-weight: {tokens.font_weight_semibold};
            }}
            
            QLabel#error_message {{
                color: {tokens.text_secondary};
                font-size: {tokens.font_size_sm};
            }}
            
            QPushButton#retry_button {{
                background: {tokens.error};
                color: white;
                border: none;
                border-radius: {tokens.radius_md};
                padding: 10px 20px;
                font-weight: {tokens.font_weight_medium};
                font-size: {tokens.font_size_base};
            }}
            
            QPushButton#retry_button:hover {{
                background: {tokens.error_hover};
            }}
            
            QPushButton#retry_button:disabled {{
                background: {tokens.interactive_disabled_bg};
                color: {tokens.interactive_disabled_text};
            }}
            
            QLabel#retry_label {{
                color: {tokens.text_muted};
                font-size: {tokens.font_size_xs};
            }}
        """
        )

    def set_error(self, message: str, retry_count: int = 0) -> None:
        """Set error state."""
        self._error_message = message
        self._retry_count = retry_count

        # Truncate long messages
        display_msg = message[:100] + "..." if len(message) > 100 else message
        self._message.setText(display_msg)
        self._message.setToolTip(message)

        if retry_count > 0:
            self._retry_label.setText(f"Attempt {retry_count}/{self._max_retries}")
            self._retry_label.show()
        else:
            self._retry_label.hide()

        # Disable retry if max reached
        if retry_count >= self._max_retries:
            self._retry_btn.setEnabled(False)
            self._retry_btn.setText("Max retries reached")
        else:
            self._retry_btn.setEnabled(True)
            self._retry_btn.setText("🔄 Retry")

    def _on_retry(self) -> None:
        self.retry_clicked.emit()


# =============================================================================
# Stale Data Banner
# =============================================================================


class StaleDataBanner(QFrame):
    """Banner indicating stale/outdated data."""

    refresh_clicked = Signal()

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service

        self.setObjectName("stale_banner")
        self.setFixedHeight(40)
        self._setup_ui()
        self._apply_style()
        self.hide()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)
        layout.setSpacing(8)

        # Icon
        icon = QLabel("⏰")
        layout.addWidget(icon)

        # Message
        self._message = QLabel("Data may be outdated")
        self._message.setObjectName("stale_message")
        layout.addWidget(self._message)

        layout.addStretch()

        # Refresh button
        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("refresh_btn")
        self._refresh_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._refresh_btn.clicked.connect(self.refresh_clicked.emit)
        layout.addWidget(self._refresh_btn)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            QFrame#stale_banner {{
                background: {tokens.warning_subtle};
                border-bottom: 1px solid {tokens.warning};
            }}
            
            QLabel#stale_message {{
                color: {tokens.warning};
                font-size: {tokens.font_size_sm};
                font-weight: {tokens.font_weight_medium};
            }}
            
            QPushButton#refresh_btn {{
                background: {tokens.warning};
                color: white;
                border: none;
                border-radius: {tokens.radius_sm};
                padding: 4px 12px;
                font-size: {tokens.font_size_xs};
                font-weight: {tokens.font_weight_medium};
            }}
            
            QPushButton#refresh_btn:hover {{
                background: {tokens.warning_hover};
            }}
        """
        )

    def show_stale(self, last_update: Optional[datetime] = None) -> None:
        """Show stale indicator with age info."""
        if last_update:
            age_seconds = (datetime.now() - last_update).total_seconds()

            if age_seconds < 60:
                age_text = f"{int(age_seconds)}s"
            elif age_seconds < 3600:
                age_text = f"{int(age_seconds / 60)}m"
            else:
                age_text = f"{int(age_seconds / 3600)}h"

            self._message.setText(f"Data is {age_text} old")
        else:
            self._message.setText("Data may be outdated")

        self.show()


# =============================================================================
# Connection Indicator
# =============================================================================


class ConnectionIndicator(QWidget):
    """Small connection status indicator."""

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._is_connected = True

        self.setFixedSize(16, 16)
        self.setToolTip("Connected")

    def set_connected(self, connected: bool) -> None:
        if connected == self._is_connected:
            return

        self._is_connected = connected
        self.setToolTip("Connected" if connected else "Disconnected")
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        tokens = self._theme_service.tokens
        color = QColor(tokens.success if self._is_connected else tokens.error)

        # Draw circle
        painter.setBrush(color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(4, 4, 8, 8)


# =============================================================================
# Enhanced Panel Header
# =============================================================================


class PanelHeader(QFrame):
    """Panel header with title, connection indicator, and close button."""

    close_clicked = Signal()

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service

        self.setObjectName("panel_header")
        self.setFixedHeight(52)
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 0, 8, 0)
        layout.setSpacing(12)

        # Title
        self._title = QLabel("Device Details")
        self._title.setObjectName("panel_title")
        layout.addWidget(self._title)

        layout.addStretch()

        # Connection indicator
        self._connection = ConnectionIndicator(self._theme_service)
        layout.addWidget(self._connection)

        # Close button
        self._close_btn = QPushButton("×")
        self._close_btn.setObjectName("close_btn")
        self._close_btn.setFixedSize(32, 32)
        self._close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._close_btn.clicked.connect(self.close_clicked.emit)
        layout.addWidget(self._close_btn)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            QFrame#panel_header {{
                background: {tokens.surface_card};
                border-bottom: 1px solid {tokens.border_default};
            }}
            
            QLabel#panel_title {{
                color: {tokens.text_primary};
                font-size: {tokens.font_size_lg};
                font-weight: {tokens.font_weight_semibold};
            }}
            
            QPushButton#close_btn {{
                background: transparent;
                border: none;
                color: {tokens.text_muted};
                font-size: 22px;
                font-weight: bold;
                border-radius: {tokens.radius_sm};
            }}
            
            QPushButton#close_btn:hover {{
                background: {tokens.interactive_hover};
                color: {tokens.text_primary};
            }}
        """
        )

    def set_connected(self, connected: bool) -> None:
        self._connection.set_connected(connected)

    def set_title(self, title: str) -> None:
        self._title.setText(title)


# =============================================================================
# Placeholder Content
# =============================================================================


class PlaceholderContent(QFrame):
    """Empty state placeholder."""

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service

        self.setObjectName("placeholder")
        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.setSpacing(16)

        # Icon
        icon = QLabel("📋")
        icon.setFont(QFont("Segoe UI Emoji", 48))
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon)

        # Text
        text = QLabel("Select a device to view details")
        text.setObjectName("placeholder_text")
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(text)

        # Hint
        hint = QLabel("Click or double-click on a device in the canvas")
        hint.setObjectName("placeholder_hint")
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            QFrame#placeholder {{
                background: transparent;
            }}
            
            QLabel#placeholder_text {{
                color: {tokens.text_secondary};
                font-size: {tokens.font_size_lg};
                font-weight: {tokens.font_weight_medium};
            }}
            
            QLabel#placeholder_hint {{
                color: {tokens.text_muted};
                font-size: {tokens.font_size_sm};
            }}
        """
        )


# =============================================================================
# Material Input Widget (Enhanced)
# =============================================================================


class MaterialInputWidget(QFrame):
    """Enhanced material input display widget."""

    def __init__(
        self,
        material: "MaterialInputModel",
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._material = material
        self._theme_service = theme_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        tokens = self._theme_service.tokens

        self.setObjectName("material_item")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"""
            QFrame#material_item {{
                background-color: {tokens.surface_elevated};
                border: 1px solid {tokens.border_subtle};
                border-radius: {tokens.radius_md};
            }}
            QFrame#material_item:hover {{
                background-color: {tokens.interactive_hover};
                border-color: {tokens.primary};
            }}
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(4)

        # Batch
        batch_layout = QHBoxLayout()
        batch_icon = QLabel("📦")
        batch_layout.addWidget(batch_icon)

        self._batch_label = QLabel(self._material.material_batch)
        self._batch_label.setStyleSheet(
            f"""
            font-weight: {tokens.font_weight_semibold};
            font-size: {tokens.font_size_sm};
            color: {tokens.text_primary};
        """
        )
        batch_layout.addWidget(self._batch_label)
        batch_layout.addStretch()
        layout.addLayout(batch_layout)

        # Name
        self._name_label = QLabel(self._material.display_name)
        self._name_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_secondary};
        """
        )
        self._name_label.setWordWrap(True)
        self._name_label.setToolTip(self._material.material_name)
        layout.addWidget(self._name_label)

        # Time
        self._time_label = QLabel(f"⏰ {self._material.formatted_time}")
        self._time_label.setStyleSheet(
            f"""
            font-size: {tokens.font_size_xs};
            color: {tokens.text_muted};
        """
        )
        layout.addWidget(self._time_label)


# =============================================================================
# Device Content (Main content when device is loaded)
# =============================================================================


class DeviceContent(QFrame):
    """Main device details content."""

    def __init__(self, theme_service: "ThemeService", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._theme_service = theme_service
        self._material_widgets: List[MaterialInputWidget] = []

        self.setObjectName("device_content")
        self._setup_ui()

    def _setup_ui(self) -> None:
        # Scroll area for content
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        content = QWidget()
        self._layout = QVBoxLayout(content)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)

        # Device info section
        self._setup_device_info()

        # Materials section
        self._setup_materials_section()

        # Metrics section
        self._setup_metrics_section()

        # Details section
        self._setup_details_section()

        self._layout.addStretch()

        scroll.setWidget(content)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll)

        self._apply_style()

    def _setup_device_info(self) -> None:
        """Setup device info header."""
        header = QHBoxLayout()

        # Name and status
        info = QVBoxLayout()
        self._name_label = QLabel("--")
        self._name_label.setObjectName("device_name")
        info.addWidget(self._name_label)

        self._last_update = QLabel("🕒 --")
        self._last_update.setObjectName("last_update")
        info.addWidget(self._last_update)

        header.addLayout(info)
        header.addStretch()

        self._status_badge = QLabel("--")
        self._status_badge.setObjectName("status_badge")
        self._status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.addWidget(self._status_badge)

        self._layout.addLayout(header)

        # Description
        self._desc = QLabel("")
        self._desc.setObjectName("description")
        self._desc.setWordWrap(True)
        self._desc.setVisible(False)
        self._layout.addWidget(self._desc)

    def _setup_materials_section(self) -> None:
        """Setup materials input section."""
        # Section header
        self._mat_header = QLabel("📥 Material Inputs")
        self._mat_header.setObjectName("section_header")
        self._layout.addWidget(self._mat_header)

        # Lot number
        self._lot_label = QLabel("🏷️ LOT: --")
        self._lot_label.setObjectName("lot_label")
        self._layout.addWidget(self._lot_label)

        # Material container
        self._mat_container = QVBoxLayout()
        self._mat_container.setSpacing(6)
        self._layout.addLayout(self._mat_container)

        # No materials label
        self._no_mat_label = QLabel("No materials loaded")
        self._no_mat_label.setObjectName("no_mat")
        self._no_mat_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._mat_container.addWidget(self._no_mat_label)

    def _setup_metrics_section(self) -> None:
        """Setup OEE/Availability/Yield metrics."""
        tokens = self._theme_service.tokens

        # OEE
        self._lbl_oee = QLabel("📊 OEE: 0%")
        self._lbl_oee.setObjectName("metric_label")
        self._layout.addWidget(self._lbl_oee)

        self._bar_oee = QProgressBar()
        self._bar_oee.setTextVisible(False)
        self._bar_oee.setFixedHeight(8)
        self._layout.addWidget(self._bar_oee)

        # Availability
        self._lbl_avail = QLabel("📈 Availability: 0%")
        self._lbl_avail.setObjectName("metric_label")
        self._layout.addWidget(self._lbl_avail)

        self._bar_avail = QProgressBar()
        self._bar_avail.setTextVisible(False)
        self._bar_avail.setFixedHeight(8)
        self._layout.addWidget(self._bar_avail)

        # Run time
        self._lbl_runtime = QLabel("⏱️ Run: 00:00:00 / Total: 00:00:00")
        self._lbl_runtime.setObjectName("runtime_label")
        self._layout.addWidget(self._lbl_runtime)

        # Yield
        self._lbl_yield = QLabel("🎯 Yield: 0%")
        self._lbl_yield.setObjectName("metric_label")
        self._layout.addWidget(self._lbl_yield)

        self._bar_yield = QProgressBar()
        self._bar_yield.setTextVisible(False)
        self._bar_yield.setFixedHeight(8)
        self._layout.addWidget(self._bar_yield)

    def _setup_details_section(self) -> None:
        """Setup details card."""
        self._details_frame = QFrame()
        self._details_frame.setObjectName("details_card")

        details_layout = QVBoxLayout(self._details_frame)
        details_layout.setContentsMargins(12, 12, 12, 12)
        details_layout.setSpacing(8)

        self._inputs = QLabel("📥 Inputs: 0")
        self._outputs = QLabel("📦 Outputs: 0")
        self._cycle = QLabel("⏱️ Cycle Time: 0s")

        details_layout.addWidget(self._inputs)
        details_layout.addWidget(self._outputs)
        details_layout.addWidget(self._cycle)

        self._layout.addWidget(self._details_frame)

        # Error status
        self._error = QLabel("✅ Healthy")
        self._error.setObjectName("error_status")
        self._error.setWordWrap(True)
        self._layout.addWidget(self._error)

    def _apply_style(self) -> None:
        tokens = self._theme_service.tokens

        self.setStyleSheet(
            f"""
            QLabel#device_name {{
                color: {tokens.text_primary};
                font-size: {tokens.font_size_lg};
                font-weight: {tokens.font_weight_bold};
            }}
            
            QLabel#last_update {{
                color: {tokens.text_muted};
                font-size: {tokens.font_size_sm};
            }}
            
            QLabel#description {{
                color: {tokens.text_secondary};
                font-size: {tokens.font_size_sm};
            }}
            
            QLabel#section_header {{
                color: {tokens.text_primary};
                font-size: {tokens.font_size_base};
                font-weight: {tokens.font_weight_semibold};
                margin-top: 8px;
            }}
            
            QLabel#lot_label {{
                color: {tokens.primary};
                font-size: {tokens.font_size_sm};
                font-weight: {tokens.font_weight_medium};
            }}
            
            QLabel#no_mat {{
                color: {tokens.text_muted};
                font-size: {tokens.font_size_sm};
                font-style: italic;
                padding: 12px;
            }}
            
            QLabel#metric_label {{
                color: {tokens.text_primary};
                font-size: {tokens.font_size_sm};
                font-weight: {tokens.font_weight_medium};
                margin-top: 4px;
            }}
            
            QLabel#runtime_label {{
                color: {tokens.text_muted};
                font-size: {tokens.font_size_xs};
            }}
            
            QProgressBar {{
                background: {tokens.interactive_hover};
                border: none;
                border-radius: 4px;
            }}
            
            QProgressBar::chunk {{
                background: {tokens.primary};
                border-radius: 4px;
            }}
            
            QFrame#details_card {{
                background: {tokens.surface_elevated};
                border: 1px solid {tokens.border_default};
                border-radius: {tokens.radius_md};
            }}
            
            QFrame#details_card QLabel {{
                color: {tokens.text_primary};
                font-size: {tokens.font_size_sm};
            }}
        """
        )

    def render_device(self, device: "DeviceDisplayModel") -> None:
        """Render device data."""
        tokens = self._theme_service.tokens

        # Header
        self._name_label.setText(str(device.display_name))

        if device.last_update:
            clean_time = str(device.last_update).replace("T", " ").split(".")[0]
            self._last_update.setText(f"🕒 {clean_time}")
        else:
            self._last_update.setText("🕒 --")

        # Status badge
        self._status_badge.setText(str(device.status_name).upper())
        self._status_badge.setStyleSheet(
            f"""
            background-color: {device.status_color};
            color: white;
            font-weight: 600;
            padding: 6px 14px;
            border-radius: 12px;
            font-size: 10px;
        """
        )

        # Description
        if device.description:
            self._desc.setText(str(device.description))
            self._desc.setVisible(True)
        else:
            self._desc.setVisible(False)

        # Materials
        self._render_materials(device.material_inputs, device.current_lot_no)

        # Metrics
        self._render_metrics(device)

        # Details
        self._inputs.setText(f"📥 Inputs: {device.input_count:,}")
        self._outputs.setText(f"📦 Outputs: {device.output_count:,}")
        self._cycle.setText(f"⏱️ Cycle Time: {device.cycle_time}s")

        # Error
        if device.last_error:
            self._error.setText(f"⚠️ {device.last_error}")
            self._error.setStyleSheet(f"color: {tokens.error}; font-weight: 600;")
        else:
            self._error.setText("✅ Healthy")
            self._error.setStyleSheet(f"color: {tokens.success};")

    def _render_materials(self, materials: Tuple, lot_no: str) -> None:
        """Render material inputs."""
        # Clear existing
        for widget in self._material_widgets:
            widget.deleteLater()
        self._material_widgets.clear()

        # Lot
        if lot_no:
            self._lot_label.setText(f"🏷️ LOT: {lot_no}")
        else:
            self._lot_label.setText("🏷️ LOT: --")

        # Materials
        has_materials = len(materials) > 0
        self._no_mat_label.setVisible(not has_materials)

        if has_materials:
            for material in materials:
                widget = MaterialInputWidget(
                    material=material,
                    theme_service=self._theme_service,
                )
                self._mat_container.insertWidget(self._mat_container.count() - 1, widget)
                self._material_widgets.append(widget)

    def _render_metrics(self, device: "DeviceDisplayModel") -> None:
        """Render OEE/Availability/Yield."""
        tokens = self._theme_service.tokens

        # OEE
        oee = float(device.oee) if device.oee else 0
        self._lbl_oee.setText(f"📊 OEE: {oee:.1f}%")
        self._bar_oee.setValue(int(min(oee, 100)))

        oee_color = tokens.success if oee > 85 else tokens.warning if oee > 60 else tokens.error
        self._bar_oee.setStyleSheet(
            f"""
            QProgressBar {{ background: {tokens.interactive_hover}; border: none; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {oee_color}; border-radius: 4px; }}
        """
        )

        # Availability
        avail = float(device.availability) if hasattr(device, "availability") else 0
        self._lbl_avail.setText(f"📈 Availability: {avail:.1f}%")
        self._bar_avail.setValue(int(min(avail, 100)))

        avail_color = tokens.success if avail > 80 else tokens.warning if avail > 50 else tokens.error
        self._bar_avail.setStyleSheet(
            f"""
            QProgressBar {{ background: {tokens.interactive_hover}; border: none; border-radius: 4px; }}
            QProgressBar::chunk {{ background: {avail_color}; border-radius: 4px; }}
        """
        )

        # Runtime
        run_time = float(device.run_time_seconds) if hasattr(device, "run_time_seconds") else 0
        total_time = float(device.total_time_seconds) if hasattr(device, "total_time_seconds") else 0
        self._lbl_runtime.setText(f"⏱️ Run: {self._format_time(run_time)} / Total: {self._format_time(total_time)}")

        # Yield
        yield_rate = float(device.yield_rate) if device.yield_rate else 0
        self._lbl_yield.setText(f"🎯 Yield: {yield_rate:.1f}%")
        self._bar_yield.setValue(int(min(yield_rate, 100)))

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format seconds to HH:MM:SS."""
        total = int(max(0, seconds))
        h = total // 3600
        m = (total % 3600) // 60
        s = total % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def clear(self) -> None:
        """Clear all content."""
        for widget in self._material_widgets:
            widget.deleteLater()
        self._material_widgets.clear()


# =============================================================================
# Enhanced Right Panel View
# =============================================================================


@dataclass(frozen=True, slots=True)
class RightPanelState:
    """Immutable right panel state."""

    is_expanded: bool
    selected_device_id: Optional[str]
    theme: str
    content_state: int = PanelState.PLACEHOLDER


class RightPanelView:
    """
    Enhanced Right Panel with Loading/Error/Stale states.

    Features:
    - Skeleton loading animation
    - Error state with retry
    - Stale data indicator
    - Connection status
    - Smooth transitions
    """

    def __init__(
        self,
        container: QFrame,
        store: "Store",
        device_vm: "DeviceListViewModel",
        shell_vm: "ShellViewModel",
        theme_service: "ThemeService",
    ):
        self._container = container
        self._store = store
        self._device_vm = device_vm
        self._shell_vm = shell_vm
        self._theme_service = theme_service

        # State
        self._state = RightPanelState(
            is_expanded=False, selected_device_id=None, theme=theme_service.current_theme, content_state=PanelState.PLACEHOLDER
        )

        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._auto_refresh_device)
        self._refresh_timer.setInterval(3000)

        self._setup_ui()
        self._bind_signals()
        self._apply_container_style()

    def _get_device_loading_state(self, device_id: str) -> Optional[Any]:
        """
        Get device loading state safely.

        Handles different attribute names in DeviceListViewModel versions.

        Returns:
            Device state object with phase/last_update, or None
        """
        if not self._device_vm:
            return None

        # Try different attribute access patterns
        try:
            # New optimized version with DeviceStateManager
            if hasattr(self._device_vm, "_state_manager"):
                return self._device_vm._state_manager.get_state(device_id)

            # Legacy version with dict-based state
            elif hasattr(self._device_vm, "_loading_state"):
                return self._device_vm._loading_state.get(device_id)

            # Method-based access
            elif hasattr(self._device_vm, "get_device_loading_phase"):

                class StateProxy:
                    def __init__(self, vm, dev_id):
                        self.phase = vm.get_device_loading_phase(dev_id)
                        self.last_update = vm.get_device_last_update(dev_id) if hasattr(vm, "get_device_last_update") else None

                return StateProxy(self._device_vm, device_id)

        except Exception as e:
            logger.debug(f"[RightPanel] State access error for {device_id}: {e}")

        return None

    def _auto_refresh_device(self) -> None:
        """Auto-refresh current device data without showing loading state."""
        if not self._state.selected_device_id:
            self._refresh_timer.stop()
            return

        if not self._state.is_expanded:
            self._refresh_timer.stop()
            return

        logger.debug(f"[RightPanel] Auto-refresh: {self._state.selected_device_id}")

        # Fetch latest data silently
        if self._device_vm:
            self._device_vm._fetch_device_details_parallel(self._state.selected_device_id)

    def _setup_ui(self) -> None:
        """Setup panel UI with stacked content."""
        # Clear existing
        if self._container.layout():
            while self._container.layout().count():
                item = self._container.layout().takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
        else:
            QVBoxLayout(self._container)

        layout = self._container.layout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self._header = PanelHeader(self._theme_service)
        self._header.close_clicked.connect(self._shell_vm.close_right_panel)
        layout.addWidget(self._header)

        # Stale banner
        self._stale_banner = StaleDataBanner(self._theme_service)
        self._stale_banner.refresh_clicked.connect(self._on_refresh)
        layout.addWidget(self._stale_banner)

        # Stacked content
        self._stack = QStackedWidget()
        layout.addWidget(self._stack, 1)

        # 0: Placeholder
        self._placeholder = PlaceholderContent(self._theme_service)
        self._stack.addWidget(self._placeholder)

        # 1: Loading skeleton
        self._skeleton = DeviceDetailSkeleton(self._theme_service)
        self._stack.addWidget(self._skeleton)

        # 2: Error state
        self._error_state = ErrorStateWidget(self._theme_service)
        self._error_state.retry_clicked.connect(self._on_retry)
        self._stack.addWidget(self._error_state)

        # 3: Device content
        self._content = DeviceContent(self._theme_service)
        self._stack.addWidget(self._content)

        # Initial state
        self._stack.setCurrentIndex(PanelState.PLACEHOLDER)

    def _bind_signals(self) -> None:
        """Bind to ViewModel signals."""
        self._device_vm.selectionChanged.connect(self._on_selection_changed)
        self._device_vm.deviceLoadingChanged.connect(self._on_loading_changed)
        self._device_vm.deviceErrorChanged.connect(self._on_error_changed)
        self._device_vm.materialInputsChanged.connect(self._on_materials_changed)
        self._device_vm.connectionStateChanged.connect(self._on_connection_changed)
        self._device_vm.staleDataDetected.connect(self._on_stale_detected)
        self._device_vm.availabilityChanged.connect(self._on_availability_changed)

        self._shell_vm.themeChanged.connect(self._on_theme_changed)
        self._shell_vm.rightPanelChanged.connect(self._on_panel_changed)

    def _apply_container_style(self) -> None:
        """Apply container styling."""
        tokens = self._theme_service.tokens

        self._container.setStyleSheet(
            f"""
            QFrame#right_slide_menu_frame {{
                background-color: {tokens.surface_panel};
                border: none;
                border-left: 1px solid {tokens.border_default};
            }}
        """
        )

    # =========================================================================
    # Signal Handlers
    # =========================================================================

    @Slot(object)
    def _on_selection_changed(self, selection) -> None:
        """Handle device selection with safe state access."""
        if not selection.has_selection:
            self._state = RightPanelState(
                is_expanded=self._state.is_expanded, selected_device_id=None, theme=self._state.theme, content_state=PanelState.PLACEHOLDER
            )
            self._stack.setCurrentIndex(PanelState.PLACEHOLDER)
            self._stale_banner.hide()
            self._header.set_title("Device Details")
            self._refresh_timer.stop()
            return

        device_id = selection.selected_device_id

        self._state = RightPanelState(
            is_expanded=self._state.is_expanded, selected_device_id=device_id, theme=self._state.theme, content_state=self._state.content_state
        )

        if self._state.is_expanded:
            self._refresh_timer.start()

        # Check loading state safely
        if self._device_vm.is_device_loading(device_id):
            self._stack.setCurrentIndex(PanelState.LOADING)
            self._header.set_title(f"Loading {device_id}...")
            return

        # Check error state safely
        error = self._device_vm.get_device_error(device_id)
        if error:
            # Get retry count safely
            retry_count = 0
            try:
                state = self._get_device_loading_state(device_id)
                if state and hasattr(state, "retry_count"):
                    retry_count = state.retry_count
            except Exception:
                pass

            self._error_state.set_error(error, retry_count)
            self._stack.setCurrentIndex(PanelState.ERROR)
            self._header.set_title(f"Error - {device_id}")
            return

        # Show content
        device = self._device_vm.selected_device
        if device:
            self._content.render_device(device)
            self._stack.setCurrentIndex(PanelState.CONTENT)
            self._header.set_title(device_id)

            # Check stale state safely
            if self._device_vm.is_device_stale(device_id):
                last_update = None
                try:
                    state = self._get_device_loading_state(device_id)
                    if state:
                        if hasattr(state, "last_update"):
                            last_update = state.last_update
                        elif isinstance(state, dict):
                            last_update = state.get("last_update")
                except Exception:
                    pass

                self._stale_banner.show_stale(last_update)
            else:
                self._stale_banner.hide()
        else:
            self._stack.setCurrentIndex(PanelState.LOADING)
            self._header.set_title(f"Loading {device_id}...")

    @Slot(str, bool)
    def _on_loading_changed(self, device_id: str, is_loading: bool) -> None:
        """Handle loading state change."""
        if device_id != self._state.selected_device_id:
            return

        if is_loading:
            self._stack.setCurrentIndex(PanelState.LOADING)
            self._header.set_title(f"Loading {device_id}...")
        else:
            # Trigger content update
            device = self._device_vm.selected_device
            if device:
                self._content.render_device(device)
                self._stack.setCurrentIndex(PanelState.CONTENT)
                self._header.set_title(device_id)
                self._stale_banner.hide()

    @Slot(str, str)
    def _on_error_changed(self, device_id: str, error: str) -> None:
        """Handle error state with safe retry count access."""
        if device_id != self._state.selected_device_id:
            return

        retry_count = 0
        try:
            state = self._get_device_loading_state(device_id)
            if state and hasattr(state, "retry_count"):
                retry_count = state.retry_count
        except Exception:
            pass

        self._error_state.set_error(error, retry_count)
        self._stack.setCurrentIndex(PanelState.ERROR)
        self._header.set_title(f"Error - {device_id}")

    @Slot(str, list)
    def _on_materials_changed(self, device_id: str, materials: List) -> None:
        """Handle materials update."""
        if device_id != self._state.selected_device_id:
            return

        device = self._device_vm.selected_device
        if device and self._stack.currentIndex() == PanelState.CONTENT:
            self._content.render_device(device)

    @Slot(bool)
    def _on_connection_changed(self, connected: bool) -> None:
        """Handle connection state."""
        self._header.set_connected(connected)

    @Slot(list)
    def _on_stale_detected(self, stale_devices: List[str]) -> None:
        """Handle stale data detection with safe state access."""
        if self._state.selected_device_id in stale_devices:
            last_update = None
            try:
                state = self._get_device_loading_state(self._state.selected_device_id)
                if state:
                    if hasattr(state, "last_update"):
                        last_update = state.last_update
                    elif isinstance(state, dict):
                        last_update = state.get("last_update")
            except Exception:
                pass

            self._stale_banner.show_stale(last_update)

    @Slot(str, object)
    def _on_availability_changed(self, device_id: str, data: dict) -> None:
        """Handle availability update."""
        if device_id != self._state.selected_device_id:
            return

        device = self._device_vm.selected_device
        if device and self._stack.currentIndex() == PanelState.CONTENT:
            self._content.render_device(device)
            self._stale_banner.hide()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        """Handle theme change."""
        if theme == self._state.theme:
            return

        self._state = RightPanelState(
            is_expanded=self._state.is_expanded,
            selected_device_id=self._state.selected_device_id,
            theme=theme,
            content_state=self._state.content_state,
        )

        self._apply_container_style()
        # Components handle their own theme updates

    @Slot(bool)
    def _on_panel_changed(self, expanded: bool) -> None:
        """Handle panel expansion."""
        self._state = RightPanelState(
            is_expanded=expanded,
            selected_device_id=self._state.selected_device_id if expanded else None,
            theme=self._state.theme,
            content_state=self._state.content_state,
        )

        width = Layout.RIGHT_PANEL_EXPANDED_WIDTH if expanded else Layout.RIGHT_PANEL_COLLAPSED_WIDTH
        self._container.setFixedWidth(width)

        if expanded and self._state.selected_device_id:
            logger.debug(f"[RightPanel] Start auto-refresh for {self._state.selected_device_id}")
            self._refresh_timer.start()
        else:
            logger.debug("[RightPanel] Stop auto-refresh")
            self._refresh_timer.stop()

    def _on_retry(self) -> None:
        """Handle retry click."""
        if self._state.selected_device_id:
            self._stack.setCurrentIndex(PanelState.LOADING)
            self._device_vm.retry_device(self._state.selected_device_id)

    def _on_refresh(self) -> None:
        """Handle refresh click."""
        if self._state.selected_device_id:
            self._device_vm._fetch_device_details_parallel(self._state.selected_device_id)

    # =========================================================================
    # Legacy Compatibility
    # =========================================================================

    def render(self, state: Dict[str, Any]) -> None:
        """Render from global state (legacy compatibility)."""
        # Most updates now come through ViewModel signals
        # This method ensures compatibility with MainWindow pattern
        pass

    def dispose(self) -> None:
        """Clean up resources."""
        if self._refresh_timer:
            self._refresh_timer.stop()
        self._content.clear()

        try:
            self._device_vm.selectionChanged.disconnect(self._on_selection_changed)
            self._device_vm.deviceLoadingChanged.disconnect(self._on_loading_changed)
            self._device_vm.deviceErrorChanged.disconnect(self._on_error_changed)
            self._device_vm.materialInputsChanged.disconnect(self._on_materials_changed)
            self._device_vm.connectionStateChanged.disconnect(self._on_connection_changed)
            self._device_vm.staleDataDetected.disconnect(self._on_stale_detected)
            self._device_vm.availabilityChanged.disconnect(self._on_availability_changed)
            self._shell_vm.themeChanged.disconnect(self._on_theme_changed)
            self._shell_vm.rightPanelChanged.disconnect(self._on_panel_changed)
        except (RuntimeError, TypeError):
            pass


__all__ = [
    "RightPanelView",
    "DeviceDetailSkeleton",
    "ErrorStateWidget",
    "StaleDataBanner",
    "MaterialInputWidget",
]
