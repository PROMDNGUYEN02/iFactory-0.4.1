# File: src/iFactory/presentation/managers/animation_manager.py
"""
Animation Manager - Manages smooth animations for UI elements.
"""
from __future__ import annotations
from typing import Callable, Optional

from PySide6.QtCore import (
    QParallelAnimationGroup,
    QVariantAnimation,
    Signal,
    QEasingCurve,
)
from PySide6.QtWidgets import QFrame


class AnimationTarget:
    """Animation target identifier."""

    LEFT_MENU = 0
    RIGHT_PANEL = 1


class AnimationManager:
    """Manages smooth animations for UI elements."""

    __slots__ = (
        "_duration",
        "_left_group",
        "_left_min",
        "_left_max",
        "_right_group",
        "_right_min",
        "_right_max",
        "_left_min_cb",
        "_left_max_cb",
        "_left_done_cb",
        "_right_min_cb",
        "_right_max_cb",
        "_right_done_cb",
    )

    def __init__(self, duration: int = 200):
        self._duration = duration
        self._left_group = QParallelAnimationGroup()
        self._left_min = self._create_animation()
        self._left_max = self._create_animation()
        self._left_group.addAnimation(self._left_min)
        self._left_group.addAnimation(self._left_max)

        self._right_group = QParallelAnimationGroup()
        self._right_min = self._create_animation()
        self._right_max = self._create_animation()
        self._right_group.addAnimation(self._right_min)
        self._right_group.addAnimation(self._right_max)

        self._left_min_cb: Optional[Callable[[int], None]] = None
        self._left_max_cb: Optional[Callable[[int], None]] = None
        self._left_done_cb: Optional[Callable[[], None]] = None
        self._right_min_cb: Optional[Callable[[int], None]] = None
        self._right_max_cb: Optional[Callable[[int], None]] = None
        self._right_done_cb: Optional[Callable[[], None]] = None

        self._left_min.valueChanged.connect(
            lambda v: self._left_min_cb and self._left_min_cb(v)
        )
        self._left_max.valueChanged.connect(
            lambda v: self._left_max_cb and self._left_max_cb(v)
        )
        self._right_min.valueChanged.connect(
            lambda v: self._right_min_cb and self._right_min_cb(v)
        )
        self._right_max.valueChanged.connect(
            lambda v: self._right_max_cb and self._right_max_cb(v)
        )
        self._left_group.finished.connect(
            lambda: self._left_done_cb and self._left_done_cb()
        )
        self._right_group.finished.connect(
            lambda: self._right_done_cb and self._right_done_cb()
        )

    def _create_animation(self) -> QVariantAnimation:
        anim = QVariantAnimation()
        anim.setDuration(self._duration)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        return anim

    def set_callbacks(
        self,
        target: AnimationTarget,
        min_callback: Optional[Callable[[int], None]] = None,
        max_callback: Optional[Callable[[int], None]] = None,
        finished_callback: Optional[Callable[[], None]] = None,
    ) -> None:
        """Set animation callbacks for target."""
        if target == AnimationTarget.LEFT_MENU:
            self._left_min_cb = min_callback
            self._left_max_cb = max_callback
            self._left_done_cb = finished_callback
        elif target == AnimationTarget.RIGHT_PANEL:
            self._right_min_cb = min_callback
            self._right_max_cb = max_callback
            self._right_done_cb = finished_callback

    def animate(
        self, target: AnimationTarget, frame: QFrame, target_width: int
    ) -> None:
        """Start animation to target width."""
        current = frame.width()
        if current == target_width:
            return

        if target == AnimationTarget.LEFT_MENU:
            group, min_anim, max_anim = self._left_group, self._left_min, self._left_max
        else:
            group, min_anim, max_anim = (
                self._right_group,
                self._right_min,
                self._right_max,
            )

        group.stop()
        for anim in (min_anim, max_anim):
            anim.setStartValue(current)
            anim.setEndValue(target_width)
        group.start()

    def set_immediate(self, frame: QFrame, width: int) -> None:
        """Set width immediately without animation."""
        frame.setMinimumWidth(width)
        frame.setMaximumWidth(width)

    def stop_all(self) -> None:
        """Stop all animations."""
        self._left_group.stop()
        self._right_group.stop()

    def is_animating(self, target: AnimationTarget) -> bool:
        """Check if target is animating."""
        group = (
            self._left_group
            if target == AnimationTarget.LEFT_MENU
            else self._right_group
        )
        return group.state() == QParallelAnimationGroup.State.Running
