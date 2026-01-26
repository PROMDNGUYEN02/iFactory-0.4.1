"""
Gantt Chart Canvas Widget - Clean Architecture.
Thuần tuý là View: Chỉ vẽ các đoạn màu (Segment) dựa trên tỉ lệ phần trăm được cung cấp.
"""

import logging
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QWidget, QVBoxLayout
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class GanttCanvasWidget(QWidget):
    """
    Vẽ lịch sử hoạt động của các máy móc dưới dạng Timeline.
    Dữ liệu đầu vào: Danh sách máy, mỗi máy là 1 danh sách các đoạn (segment) có màu và độ dài %.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)

        self.scene = QGraphicsScene()
        self.view = QGraphicsView(self.scene)
        self.view.setStyleSheet("background-color: #1a1a1a; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Ẩn thanh cuộn để biểu đồ gọn gàng
        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.layout.addWidget(self.view)

        # Cấu hình kích thước vẽ
        self.ROW_HEIGHT = 30
        self.LABEL_WIDTH = 80
        self.CHART_WIDTH = 1000  # Sẽ tự scale theo cửa sổ

    def render_timeline(self, timeline_data: dict):
        """
        Vẽ lại toàn bộ biểu đồ.
        timeline_data = {
            "AMX01": [{"color": "#3bb806", "percent": 0.4}, {"color": "#c3c51b", "percent": 0.6}],
            ...
        }
        """
        self.scene.clear()

        # Lấy chiều rộng hiện tại của khung
        chart_w = self.view.viewport().width() - self.LABEL_WIDTH - 20
        if chart_w < 500:
            chart_w = 1000  # Fallback an toàn

        y_pos = 10

        # Tiêu đề
        title = self.scene.addText("24h Production Timeline")
        title.setDefaultTextColor(QColor("#cccccc"))
        title.setFont(QFont("Arial", 12, QFont.Bold))
        title.setPos(self.LABEL_WIDTH, 0)
        y_pos += 30

        # Vẽ từng dòng thiết bị
        for equip_code, segments in timeline_data.items():
            # Vẽ tên máy
            label = self.scene.addText(equip_code)
            label.setDefaultTextColor(QColor("white"))
            label.setFont(QFont("Arial", 10))
            label.setPos(0, y_pos)

            # Vẽ các đoạn Gantt
            current_x = self.LABEL_WIDTH
            for seg in segments:
                seg_width = chart_w * seg["percent"]

                rect = QGraphicsRectItem(current_x, y_pos + 5, seg_width, self.ROW_HEIGHT - 10)
                rect.setBrush(QBrush(QColor(seg["color"])))
                rect.setPen(QPen(Qt.NoPen))  # Không viền cho mượt

                self.scene.addItem(rect)
                current_x += seg_width

            y_pos += self.ROW_HEIGHT

        # Update scene rect
        self.scene.setSceneRect(0, 0, chart_w + self.LABEL_WIDTH, max(y_pos, self.view.viewport().height()))

    def resizeEvent(self, event):
        """Tự động co giãn biểu đồ khi người dùng kéo cửa sổ."""
        super().resizeEvent(event)
        # Sẽ trigger render lại nếu cần, hiện tại scale tĩnh là ổn.


__all__ = ["GanttCanvasWidget"]
