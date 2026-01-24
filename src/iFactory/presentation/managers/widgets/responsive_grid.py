"""Responsive grid layout for device widgets."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QWidget, QGridLayout, QVBoxLayout
from typing import List


class ResponsiveGridWidget(QWidget):
    """Auto-adjusting grid for device widgets."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.cards: List[QWidget] = []
        self.min_card_width = 180
        self.card_spacing = 12
        self.cols_cache = 1
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(8, 8, 8, 8)
        self.grid_widget = QWidget()
        self.main_layout.addWidget(self.grid_widget)
        self.main_layout.addStretch()
        self.resize_timer = QTimer()
        self.resize_timer.setSingleShot(True)
        self.resize_timer.timeout.connect(self.updateLayout)
        self.updateLayout()

    def addCard(self, card: QWidget):
        """Add card to grid."""
        self.cards.append(card)
        card.setParent(self.grid_widget)
        self.updateLayout()

    def removeCard(self, card: QWidget):
        """Remove card from grid."""
        if card in self.cards:
            self.cards.remove(card)
            card.setParent(None)
            self.updateLayout()

    def updateLayout(self):
        """Recalculate grid layout based on available width."""
        if not self.cards:
            return
        available_width = max(self.width(), 400)
        new_cols = max(1, available_width // (self.min_card_width + self.card_spacing))
        layout = self.grid_widget.layout()
        if new_cols == self.cols_cache and layout and (layout.count() == len(self.cards)):
            return
        self.cols_cache = new_cols
        if self.grid_widget.layout():
            while self.grid_widget.layout().count():
                item = self.grid_widget.layout().takeAt(0)
                if item.widget():
                    item.widget().setParent(None)
            QWidget().setLayout(self.grid_widget.layout())
        grid = QGridLayout(self.grid_widget)
        grid.setSpacing(self.card_spacing)
        grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        for i, card in enumerate(self.cards):
            row = i // new_cols
            col = i % new_cols
            grid.addWidget(card, row, col)
        for col in range(new_cols):
            grid.setColumnStretch(col, 1)

    def resizeEvent(self, event):
        """Handle resize with debouncing."""
        super().resizeEvent(event)
        self.resize_timer.start(100)

    def clear(self):
        """Clear all cards."""
        for card in self.cards[:]:
            self.removeCard(card)
