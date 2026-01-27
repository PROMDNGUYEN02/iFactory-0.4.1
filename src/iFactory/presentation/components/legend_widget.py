from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt


class LegendItem(QWidget):
    def __init__(self, color: str, label: str, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        indicator = QFrame()
        indicator.setFixedSize(16, 16)
        indicator.setStyleSheet(f"background-color: {color}; border-radius: 3px;")

        text = QLabel(label)
        text.setStyleSheet("color: #333; font-size: 12px;")

        layout.addWidget(indicator)
        layout.addWidget(text)


class LegendWidget(QWidget):
    """
    Displays color coding for status.
    Configuration driven, not domain driven.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(10, 5, 10, 5)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignLeft)

        # Hardcoded for Presentation display, matching standard industrial colors
        self.add_item("#4CAF50", "Running")
        self.add_item("#F44336", "Alarm")
        self.add_item("#FFC107", "Idle/Stop")
        self.add_item("#9E9E9E", "Offline")

    def add_item(self, color: str, label: str):
        item = LegendItem(color, label)
        self._layout.addWidget(item)
