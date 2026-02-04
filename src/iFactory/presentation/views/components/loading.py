# File: presentation/views/components/loading.py
"""
Extended Loading State Components.

Additional loading components beyond base.py.
- DeviceCardSkeleton
- GanttRowSkeleton
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QFrame, QVBoxLayout, QHBoxLayout

# Import base components from base.py
from .base import SkeletonLoader


class DeviceCardSkeleton(QFrame):
    """
    Skeleton for device card loading state.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setFixedSize(140, 100)
        self.setStyleSheet(
            """
            QFrame {
                background: #FAFAFA;
                border: 1px solid #E0E0E0;
                border-radius: 8px;
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        # Icon skeleton
        icon_skeleton = SkeletonLoader(40, 40, rounded=True)
        layout.addWidget(icon_skeleton, alignment=Qt.AlignmentFlag.AlignCenter)

        # Label skeleton
        label_skeleton = SkeletonLoader(80, 14, rounded=True)
        layout.addWidget(label_skeleton, alignment=Qt.AlignmentFlag.AlignCenter)

        # Status skeleton
        status_skeleton = SkeletonLoader(60, 10, rounded=True)
        layout.addWidget(status_skeleton, alignment=Qt.AlignmentFlag.AlignCenter)


class GanttRowSkeleton(QFrame):
    """
    Skeleton for Gantt chart row.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self.setFixedHeight(50)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # Label skeleton
        label = SkeletonLoader(50, 30, rounded=True)
        layout.addWidget(label)

        # Timeline skeleton with segments
        timeline = QWidget()
        timeline_layout = QHBoxLayout(timeline)
        timeline_layout.setContentsMargins(0, 0, 0, 0)
        timeline_layout.setSpacing(2)

        for width in [80, 120, 60, 200, 40]:
            segment = SkeletonLoader(width, 26, rounded=True)
            timeline_layout.addWidget(segment)

        timeline_layout.addStretch()
        layout.addWidget(timeline, 1)


__all__ = [
    "DeviceCardSkeleton",
    "GanttRowSkeleton",
]
