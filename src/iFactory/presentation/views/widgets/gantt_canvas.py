"""
Gantt Chart Canvas Widget - Max Level UX.
Tích hợp: Lưới thời gian (Time Ruler), Tooltip tương tác hiển thị dữ liệu thực, Current Time Indicator.
"""

import logging
from datetime import datetime
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsRectItem, QGraphicsTextItem, QWidget, QVBoxLayout, QToolTip
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QBrush, QCursor
from PySide6.QtCore import Qt

logger = logging.getLogger(__name__)


class GanttSegmentItem(QGraphicsRectItem):
    """Segment có khả năng tương tác để hiện Tooltip dữ liệu thực"""

    def __init__(self, x, y, w, h, segment_data):
        super().__init__(x, y, w, h)
        self.setBrush(QBrush(QColor(segment_data["color"])))
        self.setPen(QPen(Qt.NoPen))
        self.setAcceptHoverEvents(True)
        self.data = segment_data

    def hoverEnterEvent(self, event):
        self.setOpacity(0.8)
        # Hiển thị tooltip với dữ liệu thực từ Backend
        tooltip_html = f"""
        <div style='background:#2c3e50; color:white; padding:5px; border-radius:4px;'>
            <b>Trạng thái:</b> {self.data.get('status_name', 'Hoạt động')}<br>
            <b>Bắt đầu:</b> {self.data.get('start_time', 'N/A')}<br>
            <b>Kết thúc:</b> {self.data.get('end_time', 'N/A')}<br>
            <b>Sản lượng:</b> {self.data.get('yield', 0)} sp
        </div>
        """
        QToolTip.showText(QCursor.pos(), tooltip_html)
        super().hoverEnterEvent(event)

    def hoverLeaveEvent(self, event):
        self.setOpacity(1.0)
        QToolTip.hideText()
        super().hoverLeaveEvent(event)


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
        self.view.setStyleSheet("background-color: transparent; border: none;")
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)

        self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self.layout.addWidget(self.view)

        self.ROW_HEIGHT = 40
        self.LABEL_WIDTH = 90

    def render_timeline(self, timeline_data: dict):
        self.scene.clear()

        view_rect = self.view.viewport().rect()
        chart_w = max(view_rect.width() - self.LABEL_WIDTH - 20, 800)

        y_pos = 40  # Dành không gian cho Ruler

        # 1. Vẽ Time Ruler & Grid (Lưới giờ thực tế - 24h)
        grid_pen = QPen(QColor("#404040"), 1, Qt.DotLine)
        for hour in range(0, 25, 2):  # Vẽ lưới mỗi 2 tiếng
            x = self.LABEL_WIDTH + (hour / 24.0) * chart_w
            # Vẽ đường lưới dọc
            self.scene.addLine(x, y_pos, x, y_pos + len(timeline_data) * self.ROW_HEIGHT, grid_pen)
            # Vẽ nhãn giờ
            time_lbl = self.scene.addText(f"{hour:02d}:00")
            time_lbl.setDefaultTextColor(QColor("#888888"))
            time_lbl.setFont(QFont("Arial", 8))
            time_lbl.setPos(x - 15, 15)

        # 2. Render Máy & Dữ liệu
        for equip_code, segments in timeline_data.items():
            # Tên máy
            label = self.scene.addText(equip_code)
            label.setDefaultTextColor(QColor("#cccccc"))
            label.setFont(QFont("Arial", 10, QFont.Bold))
            label.setPos(5, y_pos + 10)

            # Vẽ các đoạn Gantt Tương tác
            current_x = self.LABEL_WIDTH
            for seg in segments:
                seg_width = chart_w * seg["percent"]

                # Khởi tạo Segment Tương tác
                item = GanttSegmentItem(current_x, y_pos + 8, seg_width, self.ROW_HEIGHT - 16, seg)
                self.scene.addItem(item)

                current_x += seg_width

            y_pos += self.ROW_HEIGHT

        # 3. Vẽ Current Time Indicator (Đường hiện tại)
        now = datetime.now()
        hours_passed = now.hour + now.minute / 60.0
        now_x = self.LABEL_WIDTH + (hours_passed / 24.0) * chart_w

        now_line = self.scene.addLine(now_x, 30, now_x, y_pos, QPen(QColor("#e74c3c"), 2))
        now_lbl = self.scene.addText("NOW")
        now_lbl.setDefaultTextColor(QColor("#e74c3c"))
        now_lbl.setFont(QFont("Arial", 8, QFont.Bold))
        now_lbl.setPos(now_x - 15, 15)

        self.scene.setSceneRect(0, 0, chart_w + self.LABEL_WIDTH, y_pos + 20)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.view.fitInView(self.scene.sceneRect(), Qt.IgnoreAspectRatio)


__all__ = ["GanttCanvasWidget"]
