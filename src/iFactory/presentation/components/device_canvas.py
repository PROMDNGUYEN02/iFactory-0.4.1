from typing import List, Dict
from PySide6.QtWidgets import QWidget
from PySide6.QtGui import QPainter, QPaintEvent, QColor, QFont, QPen, QBrush
from PySide6.QtCore import Qt, QRect, Signal

from iFactory.presentation.viewmodels.device_viewmodel import DeviceViewModel


class DeviceCanvas(QWidget):
    """
    Visual component rendering a grid of devices.
    Purely presentation; contains no business logic.
    """

    device_clicked = Signal(str)  # Emits equipment_code

    def __init__(self, parent=None):
        super().__init__(parent)
        self._devices: List[DeviceViewModel] = []
        self._cell_width = 120
        self._cell_height = 100
        self._padding = 10
        self.setMouseTracking(True)

    def update_devices(self, devices: List[DeviceViewModel]):
        self._devices = devices
        self.update()  # Trigger repaint

    def paintEvent(self, event: QPaintEvent):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        cols = max(1, width // (self._cell_width + self._padding))

        for index, device in enumerate(self._devices):
            row = index // cols
            col = index % cols

            x = self._padding + col * (self._cell_width + self._padding)
            y = self._padding + row * (self._cell_height + self._padding)

            rect = QRect(x, y, self._cell_width, self._cell_height)
            self._draw_device_card(painter, rect, device)

    def _draw_device_card(self, painter: QPainter, rect: QRect, device: DeviceViewModel):
        # Background
        color = QColor(device.status_color)
        painter.setBrush(QBrush(color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 8, 8)

        # Border
        painter.setPen(QPen(Qt.GlobalColor.gray, 1))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(rect, 8, 8)

        # Text: Code
        painter.setPen(Qt.GlobalColor.white)
        font = QFont("Arial", 10, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(rect.adjusted(5, 5, -5, -20), Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft, device.equipment_code)

        # Text: Status
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)
        painter.drawText(rect.adjusted(5, 25, -5, -5), Qt.AlignmentFlag.AlignCenter, device.status_display)

    def mousePressEvent(self, event):
        x = event.pos().x()
        y = event.pos().y()

        width = self.width()
        cols = max(1, width // (self._cell_width + self._padding))

        col = (x - self._padding) // (self._cell_width + self._padding)
        row = (y - self._padding) // (self._cell_height + self._padding)

        index = row * cols + col

        if 0 <= index < len(self._devices):
            device = self._devices[index]
            self.device_clicked.emit(device.equipment_code)
