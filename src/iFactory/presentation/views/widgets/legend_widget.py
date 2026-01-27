"""
Legend Widget - Status color legend.
Theme-aware with automatic color adaptation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class LegendWidget(QWidget):
    """Status legend with color indicators."""

    STATUSES = [
        ("RUN", "#3bb806"),
        ("IDLE", "#c3c51b"),
        ("TEST", "#38c0bf"),
        ("PS", "#7a820e"),
        ("UP", "#080fac"),
        ("PD", "#631c0f"),
        ("MC", "#1a381c"),
        ("PP", "#7d1790"),
        ("BM", "#bd1e15"),
        ("PM", "#7f8174"),
        ("CM", "#030301"),
        ("N/A", "#9E9E9E"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet("background-color: transparent;")
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 5, 10, 5)
        layout.setSpacing(15)
        layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        title = QLabel("EQ\nStatus")
        title.setStyleSheet("font-weight: bold; background-color: #939892; " "padding: 2px 5px; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        for label_text, color in self.STATUSES:
            item = self._create_legend_item(label_text, color)
            layout.addWidget(item)

    def _create_legend_item(self, label_text: str, color: str) -> QWidget:
        color_box = QFrame()
        color_box.setFixedSize(16, 16)
        color_box.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: 1px solid #555;")

        lbl = QLabel(label_text)
        lbl.setStyleSheet("font-size: 11px;")

        item_layout = QHBoxLayout()
        item_layout.setContentsMargins(0, 0, 0, 0)
        item_layout.setSpacing(5)
        item_layout.addWidget(color_box)
        item_layout.addWidget(lbl)

        wrapper = QWidget()
        wrapper.setLayout(item_layout)
        return wrapper


__all__ = ["LegendWidget"]
