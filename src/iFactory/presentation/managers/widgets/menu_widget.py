"""
Menu Widget Item - Custom widget with icon, label and tooltip.

Refactor to add text labels beside icons in left menu items.
Replaces QListWidgetItem with custom widget to support icon + text.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QLabel, QWidget, QHBoxLayout

__all__ = ["MenuItemWidget"]


class MenuItemWidget(QWidget):
    """
    Custom menu item widget with icon, label, tooltip.

    Layout:
        [Icon] [Label] [Shortcut] [Spacer]
    """

    __slots__ = ("_icon", "_label", "_shortcut", "_tooltip", "_widget")

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
            icon: Resource string (e.g., ":/icon/dashboard.svg")
            label: Text label beside icon
            shortcut: Shortcut text (e.g., "Ctrl+O")
            tooltip: Full tooltip text
            parent: Parent widget
        """
        super().__init__(parent)
        self._icon = icon
        self._label = label
        self._shortcut = shortcut
        self._tooltip = tooltip

        # Setup layout
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.setSizeConstraint(QHBoxLayout.SetDefaultConstraint)

        # Create icon
        icon_widget = QLabel()
        if icon:
            icon_widget.setPixmap(QIcon(icon).pixmap(16, 16))
            icon_widget.setObjectName("menuIcon")
        icon_widget.setFixedSize(16, 16)
            layout.addWidget(icon_widget)

        # Create label
        label_widget = QLabel(label)
        label_widget.setObjectName("menuLabel")
        label_widget.setSizePolicy(
            QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        )
        layout.addWidget(label_widget)

        # Spacer
        spacer = QLabel()
        layout.addStretch()

        # Optional: shortcut
        if shortcut:
            shortcut_widget = QLabel(shortcut)
            shortcut_widget.setObjectName("menuShortcut")
            shortcut_widget.setStyleSheet("color: #999999; font-size: 11px;")
            layout.addWidget(shortcut_widget)

        # Store reference for updates
        self._widget = layout
        self._icon_widget = icon_widget
        self._label_widget = label_widget
        self._shortcut_widget = shortcut_widget

    def set_icon(self, icon: str | QIcon) -> None:
        """Update icon widget."""
        if isinstance(icon, str):
            self._icon_widget.setPixmap(QIcon(icon).pixmap(16, 16))

    def set_label(self, label: str) -> None:
        """Update label widget."""
        if self._label_widget:
            self._label_widget.setText(label)

    def set_shortcut(self, shortcut: str) -> None:
        """Update shortcut widget."""
        if self._shortcut_widget:
            self._shortcut_widget.setText(shortcut)

    def set_tooltip(self, tooltip: str) -> None:
        """Update tooltip (uses full tooltip text)."""
        self.setToolTip(tooltip)

    def get_layout(self) -> QHBoxLayout:
        """Get internal layout for external access."""
        return self._widget

    def get_icon_widget(self) -> QLabel:
        """Get icon widget."""
        return self._icon_widget

    def get_label_widget(self) -> QLabel:
        """Get label widget."""
        return self._label_widget

    def get_shortcut_widget(self) -> QLabel:
        """Get shortcut widget if exists."""
        return self._shortcut_widget if hasattr(self, "_shortcut_widget") else None

    def set_expanded(self, expanded: bool) -> None:
        """Set expanded/collapsed state (visual only)."""
        self.setProperty("expanded", expanded)
        if not expanded:
            self.style().unpolish(self)
        else:
            self.style().polish(self)
            self.style().polish(self)
            self.update()