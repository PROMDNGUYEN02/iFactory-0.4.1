"""Right panel components."""

from __future__ import annotations
import logging
from typing import Optional, Callable
from PySide6.QtCore import Qt, QSize, QTimer, QEvent
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QWidget, QFrame, QPushButton, QVBoxLayout, QHBoxLayout, QListWidget

logger = logging.getLogger(__name__)
__all__ = ["RightEdgeHoverZone", "RightMenuToggleButton", "ResizableRightPanel"]
ARROW_OPEN = ":/icon/arrow_menu_open.svg"
ARROW_CLOSE = ":/icon/arrow_menu_close.svg"


class RightEdgeHoverZone(QWidget):
    """Edge hover zone with debouncing."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setMouseTracking(True)
        self._hover_cb: Optional[Callable] = None
        self._leave_cb: Optional[Callable] = None
        self._click_cb: Optional[Callable] = None
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(100)
        self._hover_timer.timeout.connect(self._on_hover)
        self._leave_timer = QTimer(self)
        self._leave_timer.setSingleShot(True)
        self._leave_timer.setInterval(50)
        self._leave_timer.timeout.connect(self._on_leave)

    def set_hover_callback(self, cb: Callable) -> None:
        self._hover_cb = cb

    def set_leave_callback(self, cb: Callable) -> None:
        self._leave_cb = cb

    def set_click_callback(self, cb: Callable) -> None:
        self._click_cb = cb

    def _on_hover(self) -> None:
        if self._hover_cb:
            try:
                self._hover_cb()
            except Exception as e:
                logger.error(f"Hover callback error: {e}")

    def _on_leave(self) -> None:
        if self._leave_cb:
            try:
                self._leave_cb()
            except Exception as e:
                logger.error(f"Leave callback error: {e}")

    def enterEvent(self, event) -> None:
        self._leave_timer.stop()
        self._hover_timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hover_timer.stop()
        self._leave_timer.start()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._click_cb:
            try:
                self._click_cb()
            except Exception as e:
                logger.error(f"Click callback error: {e}")
        event.accept()

    def paintEvent(self, event) -> None:
        pass


class RightMenuToggleButton(QPushButton):
    """Toggle button for right menu."""

    def __init__(self, icons, parent: Optional[QWidget] = None, inside: bool = True):
        super().__init__(parent)
        self._icons = icons
        self._expanded = False
        self.setObjectName("rightMenuToggleBtn" if inside else "floatingOpenBtn")
        self.setFixedSize(16, 40)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)

    def set_expanded(self, expanded: bool) -> None:
        if self._expanded != expanded:
            self._expanded = expanded
            self._update_icon()

    def _update_icon(self) -> None:
        icon_path = ARROW_CLOSE if self._expanded else ARROW_OPEN
        size = QSize(30, 30)
        if self._icons and hasattr(self._icons, "pixmap"):
            try:
                pixmap = self._icons.pixmap(icon_path, size)
                if not pixmap.isNull():
                    self.setIcon(QIcon(pixmap))
                    self.setIconSize(size)
                    return
            except Exception:
                pass
        self.setIcon(QIcon(icon_path))
        self.setIconSize(size)

    def update_icons(self) -> None:
        self._update_icon()


class ResizableRightPanel(QFrame):
    """Resizable right panel."""

    MIN_W = 150
    MAX_W = 800
    DEF_W = 200
    HDL_W = 6

    def __init__(self, icons, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._icons = icons
        self._resizing = False
        self._start_x = 0
        self._start_width = 0
        self._resize_callback: Optional[Callable] = None
        self._content_widget: Optional[QWidget] = None
        self.setObjectName("resizableRightPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._setup_ui()

    def _setup_ui(self) -> None:
        main = QHBoxLayout(self)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)
        self._resize_handle = QFrame()
        self._resize_handle.setObjectName("resizeHandle")
        self._resize_handle.setFixedWidth(self.HDL_W)
        self._resize_handle.setCursor(Qt.CursorShape.SizeHorCursor)
        self._resize_handle.setMouseTracking(True)
        self._resize_handle.installEventFilter(self)
        btn_container = QWidget()
        btn_container.setFixedWidth(16)
        btn_layout = QVBoxLayout(btn_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.addStretch(1)
        self._toggle_button = RightMenuToggleButton(self._icons, btn_container, True)
        self._toggle_button.set_expanded(True)
        btn_layout.addWidget(self._toggle_button)
        btn_layout.addStretch(1)
        self._content_frame = QFrame()
        self._content_frame.setObjectName("rightPanelContent")
        self._content_frame.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self._content_layout = QVBoxLayout(self._content_frame)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._list_widget = QListWidget()
        self._list_widget.setObjectName("rightListWidget")
        self._list_widget.setFrameShape(QFrame.Shape.NoFrame)
        self._content_layout.addWidget(self._list_widget, 1)
        main.addWidget(self._resize_handle)
        main.addWidget(btn_container)
        main.addWidget(self._content_frame, 1)
        self.setFixedWidth(self.DEF_W)

    @property
    def toggle_button(self) -> RightMenuToggleButton:
        return self._toggle_button

    @property
    def list_widget(self) -> QListWidget:
        return self._list_widget

    @property
    def content_frame(self) -> QFrame:
        return self._content_frame

    def set_content_widget(self, widget: QWidget) -> None:
        if self._content_widget:
            self._content_layout.removeWidget(self._content_widget)
            self._content_widget.setParent(None)
        if self._list_widget:
            self._content_layout.removeWidget(self._list_widget)
            self._list_widget.hide()
        self._content_widget = widget
        self._content_layout.addWidget(widget, 1)

    def set_resize_callback(self, callback: Callable) -> None:
        self._resize_callback = callback

    def set_panel_width(self, width: int) -> None:
        width = max(self.MIN_W, min(self.MAX_W, width))
        if self.width() != width:
            self.setFixedWidth(width)

    def get_max_width(self) -> int:
        if self.parent():
            return min(self.MAX_W, int(self.parent().width() * 0.7))
        return self.MAX_W

    def update_icons(self) -> None:
        self._toggle_button.update_icons()

    def eventFilter(self, obj, event) -> bool:
        if obj is not self._resize_handle:
            return False
        event_type = event.type()
        try:
            if event_type == QEvent.Type.MouseButtonPress:
                if event.button() == Qt.MouseButton.LeftButton:
                    self._resizing = True
                    self._start_x = event.globalPosition().x()
                    self._start_width = self.width()
                    return True
            elif event_type == QEvent.Type.MouseMove and self._resizing:
                delta = self._start_x - event.globalPosition().x()
                new_width = max(self.MIN_W, min(self.get_max_width(), int(self._start_width + delta)))
                self.setFixedWidth(new_width)
                if self.parent():
                    self.move(self.parent().width() - new_width, self.y())
                return True
            elif event_type == QEvent.Type.MouseButtonRelease:
                if event.button() == Qt.MouseButton.LeftButton and self._resizing:
                    self._resizing = False
                    if self._resize_callback:
                        try:
                            self._resize_callback(self.width())
                        except Exception as e:
                            logger.error(f"Resize callback error: {e}")
                    return True
        except Exception as e:
            logger.error(f"EventFilter error: {e}")
        return False
