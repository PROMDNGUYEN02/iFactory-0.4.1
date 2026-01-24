"""
Menu Widget Item - Custom widget with icon, label, shortcut and tooltip.

Based on ExpandableMenuButton pattern but simplified.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QHBoxLayout, QIcon, QLabel, QWidget

if TYPE_CHECKING:
    from iFactory.presentation.managers.widgets.constants import ICON_SIZE

__all__ = ["MenuWidgetItem"]


class MenuWidgetItem(QWidget):
    """
    Custom menu item widget with icon, label, shortcut and tooltip.

    Layout:
        [Icon] [Label] [Shortcut]
    """

    __slots__ = ("_icon", "_label", "_shortcut", "_tooltip")

    def __init__(
        self,
        icon: str | QIcon,
        label: str = "",
        shortcut: str = "",
        tooltip: str = "",
        parent: QWidget | None = None,
    ):
        """
        Initialize menu item widget.

        Args:
            icon: QIcon or resource path string
            label: Text label beside icon
            shortcut: Shortcut hint
            tooltip: Full tooltip with all info
            parent: Parent widget
        """
        super().__init__(parent)

        # Setup layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(4)

        # Icon
        self._icon = QLabel()
        self._icon.setObjectName("menuIcon")
        self._icon.setFixedSize(ICON_SIZE, ICON_SIZE)
        self._icon.setScaledContents(True)
        if isinstance(icon, str):
            from iFactory.presentation.managers.widgets.constants import Icons
            self._icon.setPixmap(Icons.icon(icon, ICON_SIZE, ICON_SIZE))
        else:
            self._icon.setPixmap(icon)
        layout.addWidget(self._icon)

        # Label
        if label:
            self._label = QLabel(label)
            self._label.setObjectName("menuLabel")
            self._label.setSizePolicy(Qt.SizePolicy.Expanding, QSizePolicy.Expanding, QSizePolicy.Policy.Preferred)
            layout.addWidget(self._label)

        # Optional shortcut
        if shortcut:
            self._shortcut = QLabel(shortcut)
            self._shortcut.setObjectName("menuShortcut")
            self._shortcut.setVisible(bool(shortcut))
            self._shortcut.setStyleSheet("color: #9E9E9E9; font-size: 10px;")
            layout.addWidget(self._shortcut)

        # Store for external access
        self._tooltip = tooltip or ""
        self.setLayout(layout)

    def get_label_text(self) -> str:
        """Get label text."""
        return self._label.text()

    def get_shortcut_text(self) -> str:
        """Get shortcut hint."""
        return self._shortcut.text()

    def set_tooltip(self, tooltip: str) -> None:
        """Update tooltip."""
        self._tooltip = tooltip
        self.setToolTip(self.tooltip)

    def set_expanded(self, expanded: bool) -> None:
        """Set expanded/collapsed state (visual only)."""
        self.setProperty("expanded", expanded)
        if expanded:
            self.style().unpolish(self)
        else:
            self.style().polish(self)

    def update_icon(self, icon: str | QIcon) -> None:
        """Update icon."""
        if isinstance(icon, str):
            from iFactory.presentation.managers.widgets.constants import Icons
            self._icon.setPixmap(Icons.icon(icon, ICON_SIZE, ICON_SIZE))
        else:
            self._icon.setPixmap(icon)

    def update_label(self, label: str) -> None:
        """Update label text."""
        if self._label:
            self._label.setText(label)

    def update_shortcut(self, shortcut: str) -> None:
        """Update shortcut."""
        if self._shortcut:
            self._shortcut.setText(shortcut)
            self._shortcut.setVisible(bool(shortcut))

    def sizeHint(self) -> QSize:
        """Get size hint for menu item."""
        hint = super().sizeHint()
        hint.setHeight(max(hint.height(), 32))
        return hint
