"""Optimized menu widgets."""

from __future__ import annotations
from typing import TYPE_CHECKING, Optional, Callable
from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QWidget, QLabel, QStyledItemDelegate, QStyle, QStyleOptionViewItem, QApplication, QHBoxLayout, QSizePolicy

if TYPE_CHECKING:
    from PySide6.QtGui import QPainter
    from PySide6.QtCore import QModelIndex
__all__ = ["MenuDelegate", "HoverWidget", "ExpandableMenuButton", "MenuButtonWithShortcut"]


class MenuDelegate(QStyledItemDelegate):
    """Optimized menu item delegate."""

    __slots__ = ("_height", "_icon_pad")

    def __init__(self, height: int, icon_padding: int = 5, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._height = height
        self._icon_pad = icon_padding

    def paint(self, painter: QPainter, option: QStyleOptionViewItem, index: QModelIndex) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.state &= ~(QStyle.StateFlag.State_Selected | QStyle.StateFlag.State_HasFocus)
        widget = opt.widget
        style = widget.style() if widget else QApplication.style()
        collapsed = widget and widget.property("collapsed")
        if not collapsed:
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)
            return
        bg_opt = QStyleOptionViewItem(opt)
        bg_opt.text = ""
        bg_opt.icon = QIcon()
        bg_opt.features = QStyleOptionViewItem.ViewItemFeature.None_
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, bg_opt, painter, widget)
        decoration = index.data(Qt.ItemDataRole.DecorationRole)
        if not isinstance(decoration, QIcon):
            return
        size = opt.decorationSize if opt.decorationSize.isValid() else QSize(30, 30)
        mode = (
            QIcon.Mode.Disabled
            if not opt.state & QStyle.StateFlag.State_Enabled
            else QIcon.Mode.Active if opt.state & QStyle.StateFlag.State_MouseOver else QIcon.Mode.Normal
        )
        pixmap = decoration.pixmap(size, mode, QIcon.State.Off)
        inner = opt.rect.adjusted(self._icon_pad, self._icon_pad, -self._icon_pad, -self._icon_pad)
        x = inner.x() + (inner.width() - pixmap.width()) // 2
        y = inner.y() + (inner.height() - pixmap.height()) // 2
        painter.drawPixmap(x, y, pixmap)

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        hint = super().sizeHint(option, index)
        hint.setHeight(self._height)
        return hint


class HoverWidget(QWidget):
    """Base hover widget with debouncing."""

    __slots__ = ("_callback", "_hovered", "_timer")

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._callback: Optional[Callable] = None
        self._hovered = False
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._apply_hover)

    def set_click_callback(self, callback: Callable) -> None:
        self._callback = callback

    def _apply_hover(self) -> None:
        if self._hovered:
            return
        self._hovered = True
        self.setProperty("hovered", True)
        self.style().unpolish(self)
        self.style().polish(self)

    def _clear_hover(self) -> None:
        if not self._hovered:
            return
        self._hovered = False
        self.setProperty("hovered", False)
        self.style().unpolish(self)
        self.style().polish(self)

    def enterEvent(self, event) -> None:
        self._timer.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._timer.stop()
        self._clear_hover()
        super().leaveEvent(event)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._callback:
            try:
                self._callback()
            except Exception:
                pass
        event.accept()

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), 32))
        return hint


class ExpandableMenuButton(HoverWidget):
    """Menu button with expand icon."""

    __slots__ = ("_label", "_shortcut", "_icon")

    def __init__(self, title: str, shortcut: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("expandableMenuButton")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self._label = QLabel(title)
        self._label.setObjectName("expandableMenuLabel")
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._shortcut = QLabel(shortcut)
        self._shortcut.setObjectName("shortcutHint")
        self._shortcut.setVisible(bool(shortcut))
        self._icon = QLabel()
        self._icon.setObjectName("expandIcon")
        self._icon.setFixedSize(12, 12)
        self._icon.setScaledContents(True)
        layout.addWidget(self._label)
        layout.addWidget(self._shortcut)
        layout.addWidget(self._icon)

    def set_expand_icon(self, pixmap: QPixmap) -> None:
        if not pixmap.isNull():
            self._icon.setPixmap(pixmap.scaled(12, 12, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))


class MenuButtonWithShortcut(HoverWidget):
    """Simple menu button with shortcut hint."""

    __slots__ = ("_label", "_shortcut")

    def __init__(self, title: str, shortcut: str = "", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setObjectName("menuButtonWithShortcut")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(4)
        self._label = QLabel(title)
        self._label.setObjectName("menuButtonLabel")
        self._label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._shortcut = QLabel(shortcut)
        self._shortcut.setObjectName("shortcutHint")
        self._shortcut.setVisible(bool(shortcut))
        layout.addWidget(self._label)
        layout.addWidget(self._shortcut)
