"""
Legend Widget - Đã xóa màu cứng để tự động đổi màu theo Theme sáng/tối.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QFrame
from PySide6.QtCore import Qt


class LegendWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QHBoxLayout(self)
        self.layout.setContentsMargins(10, 5, 10, 5)
        self.layout.setSpacing(15)
        self.layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.setStyleSheet("background-color: transparent;")

        self.statuses = [
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

        self._setup_ui()

    def _setup_ui(self):
        title = QLabel("EQ\nStatus")
        # Giữ nguyên màu nền tiêu đề, nhưng chữ sẽ tự đổi
        title.setStyleSheet("font-weight: bold; background-color: #939892; padding: 2px 5px; border-radius: 3px;")
        title.setAlignment(Qt.AlignCenter)
        self.layout.addWidget(title)

        for label_text, color in self.statuses:
            color_box = QFrame()
            color_box.setFixedSize(16, 16)
            color_box.setStyleSheet(f"background-color: {color}; border-radius: 2px; border: 1px solid #555;")

            lbl = QLabel(label_text)
            # FIX: Xóa 'color: #ccc;' để Label tự đổi màu theo QSS của MainView
            lbl.setStyleSheet("font-size: 11px;")

            item_layout = QHBoxLayout()
            item_layout.setContentsMargins(0, 0, 0, 0)
            item_layout.setSpacing(5)
            item_layout.addWidget(color_box)
            item_layout.addWidget(lbl)

            wrapper = QWidget()
            wrapper.setLayout(item_layout)
            self.layout.addWidget(wrapper)


__all__ = ["LegendWidget"]
