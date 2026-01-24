"""Modern metric display cards."""

from PySide6.QtCore import Qt, Signal, QPropertyAnimation, QEasingCurve
from PySide6.QtGui import QFont, QColor, QPainter
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel


class MetricCard(QWidget):
    """Modern metric display card with hover effects."""

    clicked = Signal()

    def __init__(self, title: str, value: str, unit: str = "", trend: str = ""):
        super().__init__()
        self.setProperty("class", "modern-card")
        self.setMinimumHeight(120)
        self.setMaximumHeight(120)
        self.setMinimumWidth(180)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._setup_ui(title, value, unit, trend)
        self._setup_hover()

    def _setup_ui(self, title: str, value: str, unit: str, trend: str):
        """Setup card UI."""
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(16, 16, 16, 16)
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "\n            font-size: 13px; \n            color: palette(mid); /* Use palette text color for adaptability */\n            font-weight: 500;\n            background: transparent;\n        "
        )
        layout.addWidget(title_label)
        value_layout = QHBoxLayout()
        value_layout.setSpacing(4)
        self.value_label = QLabel(value)
        self.value_label.setStyleSheet(
            "\n            font-size: 28px; \n            font-weight: 700; \n            color: #0078D4;\n            background: transparent;\n        "
        )
        value_layout.addWidget(self.value_label)
        if unit:
            unit_label = QLabel(unit)
            unit_label.setStyleSheet(
                "\n                font-size: 14px; \n                color: palette(mid); \n                background: transparent;\n                padding-top: 10px;\n            "
            )
            unit_label.setAlignment(Qt.AlignmentFlag.AlignBottom)
            value_layout.addWidget(unit_label)
        value_layout.addStretch()
        layout.addLayout(value_layout)
        if trend:
            self.trend_label = QLabel(trend)
            trend_color = "#107C10" if trend.startswith("+") else "#D13438" if trend.startswith("-") else "#666666"
            self.trend_label.setStyleSheet(
                f"\n                font-size: 12px; \n                color: {trend_color}; \n                font-weight: 600;\n                background: transparent;\n            "
            )
            layout.addWidget(self.trend_label)
        else:
            self.trend_label = None
        layout.addStretch()

    def _setup_hover(self):
        """Setup hover effects."""
        self.setAttribute(Qt.WidgetAttribute.WA_Hover, True)
        self.setStyleSheet(
            '\n            QWidget[class="modern-card"] {\n                background-color: palette(window);\n                border: 1px solid palette(mid);\n                border-radius: 12px;\n            }\n            QWidget[class="modern-card"]:hover {\n                border-color: #0078D4;\n                background-color: palette(alternate-base); /* Slightly different on hover */\n            }\n        '
        )

    def update_value(self, value: str, trend: str = ""):
        """Update metric value and trend."""
        self.value_label.setText(value)
        if self.trend_label and trend:
            self.trend_label.setText(trend)
            trend_color = "#107C10" if trend.startswith("+") else "#D13438" if trend.startswith("-") else "#666666"
            self.trend_label.setStyleSheet(
                f"\n                font-size: 12px; \n                color: {trend_color}; \n                font-weight: 600;\n                background: transparent;\n            "
            )

    def mousePressEvent(self, event):
        """Handle mouse press for click signal."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)
