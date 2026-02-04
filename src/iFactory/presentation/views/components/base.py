# src/iFactory/presentation/views/components/base.py
"""
Enhanced Base Components System with UX Improvements.

New Features:
- Animation system (fade, scale, slide)
- Loading states with skeletons
- Error boundaries
- Keyboard navigation
- Focus management
- Micro-interactions
"""

from __future__ import annotations

import logging
from abc import abstractmethod
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Protocol,
    TypeVar,
    runtime_checkable,
)

from PySide6.QtCore import (
    QEasingCurve,
    QObject,
    QParallelAnimationGroup,
    QPoint,
    QPropertyAnimation,
    QRect,
    QSequentialAnimationGroup,
    QSize,
    QTimer,
    Property,
    Signal,
    Slot,
    Qt,
)
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QKeyEvent,
)
from PySide6.QtWidgets import (
    QFrame,
    QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
    QApplication,
)

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService, ThemeTokens

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ============================================================================
# Animation Constants
# ============================================================================


class AnimationDuration:
    """Standard animation durations for consistency."""

    INSTANT = 0
    FAST = 150
    NORMAL = 250
    SLOW = 400
    VERY_SLOW = 600


class AnimationEasing:
    """Standard easing curves."""

    EASE_OUT = QEasingCurve.Type.OutCubic
    EASE_IN = QEasingCurve.Type.InCubic
    EASE_IN_OUT = QEasingCurve.Type.InOutCubic
    BOUNCE = QEasingCurve.Type.OutBounce
    ELASTIC = QEasingCurve.Type.OutElastic
    OVERSHOOT = QEasingCurve.Type.OutBack


# ============================================================================
# Component Lifecycle
# ============================================================================


class ComponentState(Enum):
    """Component lifecycle states."""

    CREATED = auto()
    MOUNTING = auto()
    MOUNTED = auto()
    UPDATING = auto()
    UNMOUNTING = auto()
    UNMOUNTED = auto()
    ERROR = auto()
    LOADING = auto()  # NEW: Loading state


@dataclass
class ComponentContext:
    """Context passed to components during lifecycle."""

    theme_service: Optional["ThemeService"] = None
    parent_context: Optional["ComponentContext"] = None
    data: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from context or parent context."""
        if key in self.data:
            return self.data[key]
        if self.parent_context:
            return self.parent_context.get(key, default)
        return default

    def child_context(self, **kwargs: Any) -> "ComponentContext":
        """Create child context with additional data."""
        return ComponentContext(
            theme_service=self.theme_service,
            parent_context=self,
            data=kwargs,
        )


@runtime_checkable
class IComponent(Protocol):
    """Protocol for components with lifecycle."""

    def on_mount(self) -> None: ...
    def on_unmount(self) -> None: ...
    def on_update(self, props: Dict[str, Any]) -> None: ...


# ============================================================================
# Animation Mixins
# ============================================================================


class AnimationMixin:
    """
    Mixin providing animation capabilities to any QWidget.

    Features:
    - Fade in/out
    - Scale animations
    - Slide animations
    - Shake effect (for errors)
    - Pulse effect (for attention)
    """

    _animation_group: Optional[QParallelAnimationGroup] = None
    _opacity_effect: Optional[QGraphicsOpacityEffect] = None

    def setup_animations(self: QWidget) -> None:
        """Initialize animation system."""
        self._opacity_effect = QGraphicsOpacityEffect(self)
        self._opacity_effect.setOpacity(1.0)
        self.setGraphicsEffect(self._opacity_effect)
        self._animation_group = QParallelAnimationGroup(self)

    def fade_in(self: QWidget, duration: int = AnimationDuration.NORMAL, callback: Optional[Callable] = None) -> QPropertyAnimation:
        """Fade in animation."""
        if not self._opacity_effect:
            self.setup_animations()

        anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(AnimationEasing.EASE_OUT)

        if callback:
            anim.finished.connect(callback)

        self.show()
        anim.start()
        return anim

    def fade_out(
        self: QWidget, duration: int = AnimationDuration.NORMAL, hide_after: bool = True, callback: Optional[Callable] = None
    ) -> QPropertyAnimation:
        """Fade out animation."""
        if not self._opacity_effect:
            self.setup_animations()

        anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        anim.setDuration(duration)
        anim.setStartValue(1.0)
        anim.setEndValue(0.0)
        anim.setEasingCurve(AnimationEasing.EASE_IN)

        def on_finished():
            if hide_after:
                self.hide()
            if callback:
                callback()

        anim.finished.connect(on_finished)
        anim.start()
        return anim

    def slide_in(
        self: QWidget,
        direction: str = "left",  # left, right, top, bottom
        duration: int = AnimationDuration.NORMAL,
        callback: Optional[Callable] = None,
    ) -> QPropertyAnimation:
        """Slide in from direction."""
        current_pos = self.pos()
        start_pos = QPoint(current_pos)

        offset = 50
        if direction == "left":
            start_pos.setX(current_pos.x() - offset)
        elif direction == "right":
            start_pos.setX(current_pos.x() + offset)
        elif direction == "top":
            start_pos.setY(current_pos.y() - offset)
        elif direction == "bottom":
            start_pos.setY(current_pos.y() + offset)

        anim = QPropertyAnimation(self, b"pos")
        anim.setDuration(duration)
        anim.setStartValue(start_pos)
        anim.setEndValue(current_pos)
        anim.setEasingCurve(AnimationEasing.EASE_OUT)

        if callback:
            anim.finished.connect(callback)

        # Combine with fade
        if self._opacity_effect:
            fade = QPropertyAnimation(self._opacity_effect, b"opacity")
            fade.setDuration(duration)
            fade.setStartValue(0.0)
            fade.setEndValue(1.0)
            fade.start()

        self.show()
        anim.start()
        return anim

    def shake(self: QWidget, intensity: int = 10, duration: int = AnimationDuration.FAST) -> QSequentialAnimationGroup:
        """Shake animation for error feedback."""
        original_pos = self.pos()

        group = QSequentialAnimationGroup(self)

        for i in range(3):
            # Move right
            anim1 = QPropertyAnimation(self, b"pos")
            anim1.setDuration(duration // 6)
            anim1.setEndValue(QPoint(original_pos.x() + intensity, original_pos.y()))
            group.addAnimation(anim1)

            # Move left
            anim2 = QPropertyAnimation(self, b"pos")
            anim2.setDuration(duration // 6)
            anim2.setEndValue(QPoint(original_pos.x() - intensity, original_pos.y()))
            group.addAnimation(anim2)

            intensity = intensity // 2

        # Return to original
        final = QPropertyAnimation(self, b"pos")
        final.setDuration(duration // 6)
        final.setEndValue(original_pos)
        group.addAnimation(final)

        group.start()
        return group

    def pulse(self: QWidget, scale: float = 1.05, duration: int = AnimationDuration.FAST) -> None:
        """Pulse animation for attention."""
        if not self._opacity_effect:
            self.setup_animations()

        # Simple opacity pulse
        anim = QPropertyAnimation(self._opacity_effect, b"opacity")
        anim.setDuration(duration)
        anim.setKeyValueAt(0, 1.0)
        anim.setKeyValueAt(0.5, 0.7)
        anim.setKeyValueAt(1.0, 1.0)
        anim.setEasingCurve(AnimationEasing.EASE_IN_OUT)
        anim.start()


class HoverEffectMixin:
    """
    Mixin for hover effects.

    Provides subtle visual feedback on hover.
    """

    _hover_animation: Optional[QPropertyAnimation] = None
    _is_hovered: bool = False
    _original_style: str = ""

    def setup_hover_effect(self: QWidget, scale: float = 1.02, shadow: bool = True) -> None:
        """Setup hover effect with optional shadow."""
        self._hover_scale = scale
        self._hover_shadow = shadow

        if shadow:
            self._shadow_effect = QGraphicsDropShadowEffect(self)
            self._shadow_effect.setBlurRadius(0)
            self._shadow_effect.setColor(QColor(0, 0, 0, 30))
            self._shadow_effect.setOffset(0, 0)
            self.setGraphicsEffect(self._shadow_effect)

    def enterEvent(self: QWidget, event) -> None:
        """Handle mouse enter."""
        self._is_hovered = True
        self._animate_hover(True)
        super().enterEvent(event)

    def leaveEvent(self: QWidget, event) -> None:
        """Handle mouse leave."""
        self._is_hovered = False
        self._animate_hover(False)
        super().leaveEvent(event)

    def _animate_hover(self: QWidget, hovered: bool) -> None:
        """Animate hover state."""
        if hasattr(self, "_shadow_effect") and self._shadow_effect:
            target_blur = 15 if hovered else 0
            target_offset = 4 if hovered else 0

            # Animate blur
            blur_anim = QPropertyAnimation(self._shadow_effect, b"blurRadius")
            blur_anim.setDuration(AnimationDuration.FAST)
            blur_anim.setEndValue(target_blur)
            blur_anim.setEasingCurve(AnimationEasing.EASE_OUT)
            blur_anim.start()

            # Animate offset
            self._shadow_effect.setOffset(0, target_offset)


class RippleEffectMixin:
    """
    Mixin for material-design ripple effect on click.
    """

    _ripple_pos: QPoint = QPoint(0, 0)
    _ripple_radius: float = 0
    _ripple_opacity: float = 0
    _ripple_animation: Optional[QPropertyAnimation] = None

    def get_ripple_radius(self) -> float:
        return self._ripple_radius

    def set_ripple_radius(self, value: float) -> None:
        self._ripple_radius = value
        self.update()

    ripple_radius = Property(float, get_ripple_radius, set_ripple_radius)

    def get_ripple_opacity(self) -> float:
        return self._ripple_opacity

    def set_ripple_opacity(self, value: float) -> None:
        self._ripple_opacity = value
        self.update()

    ripple_opacity = Property(float, get_ripple_opacity, set_ripple_opacity)

    def start_ripple(self: QWidget, pos: QPoint) -> None:
        """Start ripple effect at position."""
        self._ripple_pos = pos

        # Calculate max radius
        max_dist = max(
            (pos - QPoint(0, 0)).manhattanLength(),
            (pos - QPoint(self.width(), 0)).manhattanLength(),
            (pos - QPoint(0, self.height())).manhattanLength(),
            (pos - QPoint(self.width(), self.height())).manhattanLength(),
        )

        # Animate radius
        radius_anim = QPropertyAnimation(self, b"ripple_radius")
        radius_anim.setDuration(AnimationDuration.SLOW)
        radius_anim.setStartValue(0)
        radius_anim.setEndValue(max_dist * 1.5)
        radius_anim.setEasingCurve(AnimationEasing.EASE_OUT)

        # Animate opacity
        opacity_anim = QPropertyAnimation(self, b"ripple_opacity")
        opacity_anim.setDuration(AnimationDuration.SLOW)
        opacity_anim.setStartValue(0.3)
        opacity_anim.setEndValue(0.0)
        opacity_anim.setEasingCurve(AnimationEasing.EASE_OUT)

        group = QParallelAnimationGroup(self)
        group.addAnimation(radius_anim)
        group.addAnimation(opacity_anim)
        group.start()

    def paint_ripple(self: QWidget, painter: QPainter) -> None:
        """Paint ripple effect. Call from paintEvent."""
        if self._ripple_opacity > 0:
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)

            color = QColor(255, 255, 255, int(255 * self._ripple_opacity))
            painter.setBrush(color)
            painter.setPen(Qt.PenStyle.NoPen)

            painter.drawEllipse(self._ripple_pos, int(self._ripple_radius), int(self._ripple_radius))
            painter.restore()


# ============================================================================
# Loading State Components
# ============================================================================


class SkeletonLoader(QFrame):
    """
    Skeleton loading placeholder.

    Shows animated placeholder while content loads.
    """

    def __init__(self, width: int = 100, height: int = 20, rounded: bool = True, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setFixedSize(width, height)
        self._rounded = rounded
        self._shimmer_pos = 0.0

        # Shimmer animation
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._update_shimmer)
        self._timer.start(30)

    def _update_shimmer(self) -> None:
        self._shimmer_pos += 0.02
        if self._shimmer_pos > 1.5:
            self._shimmer_pos = -0.5
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect()
        radius = 4 if self._rounded else 0

        # Base color
        painter.setBrush(QColor(200, 200, 200, 50))
        painter.setPen(Qt.PenStyle.NoPen)

        path = QPainterPath()
        path.addRoundedRect(rect, radius, radius)
        painter.drawPath(path)

        # Shimmer effect
        shimmer_width = rect.width() * 0.3
        shimmer_x = rect.width() * self._shimmer_pos

        gradient = QColor(255, 255, 255, 80)
        painter.setBrush(gradient)

        shimmer_rect = QRect(int(shimmer_x - shimmer_width / 2), 0, int(shimmer_width), rect.height())
        painter.setClipPath(path)
        painter.drawRect(shimmer_rect)

    def stop(self) -> None:
        """Stop shimmer animation."""
        self._timer.stop()


class LoadingOverlay(QFrame):
    """
    Semi-transparent loading overlay.

    Shows over content while loading.
    """

    def __init__(self, message: str = "Loading...", parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._message = message
        self.hide()

        self.setStyleSheet(
            """
            LoadingOverlay {
                background-color: rgba(0, 0, 0, 0.5);
            }
        """
        )

        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._spinner = SpinnerWidget(self)
        layout.addWidget(self._spinner, alignment=Qt.AlignmentFlag.AlignCenter)

        self._label = QLabel(message)
        self._label.setStyleSheet("color: white; font-size: 14px;")
        layout.addWidget(self._label, alignment=Qt.AlignmentFlag.AlignCenter)

    def show_loading(self, message: Optional[str] = None) -> None:
        """Show overlay with optional custom message."""
        if message:
            self._label.setText(message)
        self._spinner.start()
        self.raise_()
        self.show()

    def hide_loading(self) -> None:
        """Hide overlay."""
        self._spinner.stop()
        self.hide()

    def resizeEvent(self, event) -> None:
        """Resize to fill parent."""
        if self.parent():
            self.setGeometry(self.parent().rect())
        super().resizeEvent(event)


class SpinnerWidget(QWidget):
    """
    Animated loading spinner.
    """

    def __init__(self, parent: Optional[QWidget] = None, size: int = 32):
        super().__init__(parent)
        self.setFixedSize(size, size)
        self._angle = 0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._rotate)

    def start(self) -> None:
        self._timer.start(16)

    def stop(self) -> None:
        self._timer.stop()

    def _rotate(self) -> None:
        self._angle = (self._angle + 10) % 360
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        painter.translate(size / 2, size / 2)
        painter.rotate(self._angle)

        # Draw spinning arc
        pen_width = size / 8
        radius = (size - pen_width) / 2

        from PySide6.QtGui import QPen

        pen = QPen(QColor(255, 255, 255), pen_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)

        painter.drawArc(int(-radius), int(-radius), int(radius * 2), int(radius * 2), 0, 270 * 16)


# ============================================================================
# Mixin Classes for Non-QWidget Views
# ============================================================================


class ThemedComponentMixin:
    """
    Mixin for views that manage QWidgets but are not QWidgets themselves.
    """

    __slots__ = ("_style_cache", "_is_disposed")

    def __init__(self) -> None:
        self._style_cache: Dict[str, str] = {}
        self._is_disposed: bool = False

    def clear_style_cache(self) -> None:
        self._style_cache.clear()

    def get_cached_style(self, cache_key: str) -> Optional[str]:
        return self._style_cache.get(cache_key)

    def set_cached_style(self, cache_key: str, style: str) -> None:
        self._style_cache[cache_key] = style

    def dispose(self) -> None:
        if self._is_disposed:
            return
        self._style_cache.clear()
        self._is_disposed = True

    @property
    def is_disposed(self) -> bool:
        return self._is_disposed


class StatefulViewMixin:
    """Mixin for views that track state changes."""

    __slots__ = ("_state",)

    def __init__(self) -> None:
        self._state: Any = None

    def _states_equal(self, state1: Any, state2: Any) -> bool:
        if state1 is None or state2 is None:
            return state1 is state2
        return state1 == state2

    def _has_state_changed(self, new_state: Any) -> bool:
        return not self._states_equal(self._state, new_state)


class DisposableMixin:
    """Mixin for components that need cleanup."""

    __slots__ = ("_disposed", "_signal_connections")

    def __init__(self) -> None:
        self._disposed: bool = False
        self._signal_connections: List[tuple] = []

    def register_connection(self, signal: Any, slot: Callable) -> None:
        self._signal_connections.append((signal, slot))
        signal.connect(slot)

    def dispose(self) -> None:
        if self._disposed:
            return

        for signal, slot in self._signal_connections:
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass

        self._signal_connections.clear()
        self._disposed = True

    @property
    def is_disposed(self) -> bool:
        return self._disposed


# ============================================================================
# Base Component (Enhanced)
# ============================================================================


class BaseComponent(QWidget, AnimationMixin):
    """
    Enhanced base class for all UI components.

    Features:
    - Lifecycle hooks (mount, unmount, update)
    - Theme integration
    - Animation support
    - Loading states
    - Error boundaries
    - Keyboard navigation
    """

    # Signals
    mounted = Signal()
    unmounted = Signal()
    updated = Signal(dict)
    error_occurred = Signal(str)
    loading_changed = Signal(bool)

    def __init__(
        self,
        theme_service: Optional["ThemeService"] = None,
        context: Optional[ComponentContext] = None,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)

        # Theme
        self._theme_service = theme_service or (context.theme_service if context else None)
        self._context = context

        # Lifecycle state
        self._state = ComponentState.CREATED
        self._is_mounted = False
        self._is_loading = False
        self._props: Dict[str, Any] = {}

        # Render optimization
        self._pending_update = False
        self._update_timer: Optional[QTimer] = None
        self._batch_updates: Dict[str, Any] = {}

        # Style cache
        self._style_cache: Dict[str, str] = {}

        # Slots for content projection
        self._slots: Dict[str, QWidget] = {}

        # Loading overlay
        self._loading_overlay: Optional[LoadingOverlay] = None

        # Error state
        self._error_message: Optional[str] = None

        # Initialize animations
        self.setup_animations()

        # Setup theme binding
        if self._theme_service:
            self._theme_service.themeChanged.connect(self._on_theme_changed_internal)

    # ========================================================================
    # Loading State
    # ========================================================================

    def set_loading(self, loading: bool, message: str = "Loading...") -> None:
        """Set loading state with overlay."""
        if loading == self._is_loading:
            return

        self._is_loading = loading
        self._state = ComponentState.LOADING if loading else ComponentState.MOUNTED

        if loading:
            if not self._loading_overlay:
                self._loading_overlay = LoadingOverlay(message, self)
            self._loading_overlay.show_loading(message)
        else:
            if self._loading_overlay:
                self._loading_overlay.hide_loading()

        self.loading_changed.emit(loading)

    @property
    def is_loading(self) -> bool:
        return self._is_loading

    # ========================================================================
    # Error Handling
    # ========================================================================

    def set_error(self, error: Optional[str]) -> None:
        """Set error state."""
        self._error_message = error
        if error:
            self._state = ComponentState.ERROR
            self.error_occurred.emit(error)
            # Shake animation for error feedback
            if hasattr(self, "shake"):
                self.shake()

    def clear_error(self) -> None:
        """Clear error state."""
        self._error_message = None
        if self._is_mounted:
            self._state = ComponentState.MOUNTED

    @property
    def has_error(self) -> bool:
        return self._error_message is not None

    # ========================================================================
    # Keyboard Navigation
    # ========================================================================

    def keyPressEvent(self, event: QKeyEvent) -> None:
        """Handle keyboard navigation."""
        if event.key() == Qt.Key.Key_Escape:
            self.on_escape_pressed()
        elif event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
            self.on_enter_pressed()
        elif event.key() == Qt.Key.Key_Tab:
            self.on_tab_pressed(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
        else:
            super().keyPressEvent(event)

    def on_escape_pressed(self) -> None:
        """Override to handle Escape key."""
        pass

    def on_enter_pressed(self) -> None:
        """Override to handle Enter key."""
        pass

    def on_tab_pressed(self, shift: bool) -> None:
        """Override to handle Tab key."""
        pass

    # ========================================================================
    # Lifecycle (unchanged but with animation)
    # ========================================================================

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._is_mounted:
            self._mount()
            # Fade in on first show
            self.fade_in(AnimationDuration.FAST)

    def hideEvent(self, event) -> None:
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        self._unmount()
        super().closeEvent(event)

    def _mount(self) -> None:
        if self._is_mounted:
            return

        self._state = ComponentState.MOUNTING
        try:
            self.on_mount()
            self._is_mounted = True
            self._state = ComponentState.MOUNTED
            self.mounted.emit()

            if self._theme_service:
                self._apply_theme()

        except Exception as e:
            self._state = ComponentState.ERROR
            self._error_message = str(e)
            logger.error(f"[{self.__class__.__name__}] Mount error: {e}")
            self.error_occurred.emit(str(e))

    def _unmount(self) -> None:
        if not self._is_mounted:
            return

        self._state = ComponentState.UNMOUNTING
        try:
            self.on_unmount()
            self._is_mounted = False
            self._state = ComponentState.UNMOUNTED
            self.unmounted.emit()

            self._style_cache.clear()
            if self._update_timer:
                self._update_timer.stop()
                self._update_timer.deleteLater()
                self._update_timer = None

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Unmount error: {e}")

    def on_mount(self) -> None:
        """Called when component is mounted. Override in subclasses."""
        pass

    def on_unmount(self) -> None:
        """Called when component is unmounted. Override in subclasses."""
        pass

    def on_update(self, changed_props: Dict[str, Any]) -> None:
        """Called when props change. Override in subclasses."""
        pass

    # ========================================================================
    # Props & Updates (unchanged)
    # ========================================================================

    def set_props(self, **props: Any) -> None:
        changed = {}
        for key, value in props.items():
            if key not in self._props or self._props[key] != value:
                changed[key] = value
                self._props[key] = value

        if changed:
            self._schedule_update(changed)

    def get_prop(self, key: str, default: Any = None) -> Any:
        return self._props.get(key, default)

    def _schedule_update(self, changed: Dict[str, Any]) -> None:
        self._batch_updates.update(changed)

        if self._pending_update:
            return

        self._pending_update = True

        if not self._update_timer:
            self._update_timer = QTimer(self)
            self._update_timer.setSingleShot(True)
            self._update_timer.timeout.connect(self._flush_updates)

        self._update_timer.start(16)

    def _flush_updates(self) -> None:
        if not self._batch_updates:
            self._pending_update = False
            return

        self._state = ComponentState.UPDATING
        changed = self._batch_updates.copy()
        self._batch_updates.clear()
        self._pending_update = False

        try:
            self.on_update(changed)
            self._state = ComponentState.MOUNTED
            self.updated.emit(changed)
        except Exception as e:
            self._state = ComponentState.ERROR
            logger.error(f"[{self.__class__.__name__}] Update error: {e}")
            self.error_occurred.emit(str(e))

    def force_update(self) -> None:
        if self._update_timer:
            self._update_timer.stop()
        self._flush_updates()

    # ========================================================================
    # Theme (unchanged)
    # ========================================================================

    @Slot(str)
    def _on_theme_changed_internal(self, theme: str) -> None:
        self._style_cache.clear()
        if self._is_mounted:
            self._apply_theme()

    def _apply_theme(self) -> None:
        pass

    def _get_cached_style(self, key: str, generator: Callable[[], str]) -> str:
        if key not in self._style_cache:
            self._style_cache[key] = generator()
        return self._style_cache[key]

    @property
    def tokens(self) -> Optional["ThemeTokens"]:
        if self._theme_service:
            return self._theme_service.tokens
        return None

    @property
    def is_dark(self) -> bool:
        if self._theme_service:
            return self._theme_service.is_dark
        return False

    # ========================================================================
    # Slots (unchanged)
    # ========================================================================

    def set_slot(self, name: str, widget: QWidget) -> None:
        if name in self._slots:
            old_widget = self._slots[name]
            old_widget.setParent(None)
            old_widget.deleteLater()

        self._slots[name] = widget
        widget.setParent(self)
        self._on_slot_changed(name, widget)

    def get_slot(self, name: str) -> Optional[QWidget]:
        return self._slots.get(name)

    def _on_slot_changed(self, name: str, widget: QWidget) -> None:
        pass

    # ========================================================================
    # State
    # ========================================================================

    @property
    def component_state(self) -> ComponentState:
        return self._state

    @property
    def is_mounted(self) -> bool:
        return self._is_mounted

    def resizeEvent(self, event) -> None:
        """Resize loading overlay with component."""
        super().resizeEvent(event)
        if self._loading_overlay:
            self._loading_overlay.setGeometry(self.rect())


# ============================================================================
# Themed Variants (Enhanced)
# ============================================================================


class ThemedWidget(BaseComponent):
    """Base class for themed widgets with animations."""

    def __init__(
        self,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(theme_service=theme_service, parent=parent)

    @abstractmethod
    def _apply_theme(self) -> None:
        pass


class ThemedFrame(QFrame, AnimationMixin, HoverEffectMixin):
    """Themed frame with lifecycle hooks and animations."""

    def __init__(
        self,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._theme_service = theme_service
        self._is_themed = False
        self._style_cache: Dict[str, str] = {}

        # Initialize animations
        self.setup_animations()

        self._theme_service.themeChanged.connect(self._on_theme_changed)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._is_themed:
            self._apply_theme()
            self._is_themed = True

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._style_cache.clear()
        if self._is_themed:
            self._apply_theme()

    def _apply_theme(self) -> None:
        pass

    def _get_cached_style(self, key: str, generator: Callable[[], str]) -> str:
        if key not in self._style_cache:
            self._style_cache[key] = generator()
        return self._style_cache[key]

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens

    @property
    def is_dark(self) -> bool:
        return self._theme_service.is_dark


class ThemedButton(QPushButton, AnimationMixin, RippleEffectMixin):
    """Themed button with ripple effect and animations."""

    def __init__(
        self,
        text: str,
        theme_service: "ThemeService",
        variant: str = "default",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self._theme_service = theme_service
        self._variant = variant
        self._style_cache: Dict[str, str] = {}

        self.setup_animations()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    def mousePressEvent(self, event) -> None:
        """Start ripple on click."""
        if event.button() == Qt.MouseButton.LeftButton:
            self.start_ripple(event.pos())
        super().mousePressEvent(event)

    def paintEvent(self, event) -> None:
        """Paint with ripple effect."""
        super().paintEvent(event)
        painter = QPainter(self)
        self.paint_ripple(painter)

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._style_cache.clear()
        self._apply_theme()

    def _apply_theme(self) -> None:
        style = self._theme_service.get_button_style(self._variant)
        self.setStyleSheet(style)

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens

    def set_variant(self, variant: str) -> None:
        if variant != self._variant:
            self._variant = variant
            self._apply_theme()


class ThemedLabel(QLabel, AnimationMixin):
    """Themed label with animations."""

    def __init__(
        self,
        text: str,
        theme_service: "ThemeService",
        variant: str = "default",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self._theme_service = theme_service
        self._variant = variant
        self._style_cache: Dict[str, str] = {}

        self.setup_animations()
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._style_cache.clear()
        self._apply_theme()

    def _apply_theme(self) -> None:
        style = self._theme_service.get_label_style(self._variant)
        self.setStyleSheet(style)

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens

    def set_variant(self, variant: str) -> None:
        if variant != self._variant:
            self._variant = variant
            self._apply_theme()

    def set_text_animated(self, text: str) -> None:
        """Set text with fade animation."""

        def update_text():
            self.setText(text)
            self.fade_in(AnimationDuration.FAST)

        self.fade_out(AnimationDuration.FAST, hide_after=False, callback=update_text)


# ============================================================================
# Component Utilities (unchanged)
# ============================================================================


class ComponentRegistry:
    """Registry for component types."""

    _instance: Optional["ComponentRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._components = {}
        return cls._instance

    def register(self, name: str, component_class: type) -> None:
        self._components[name] = component_class

    def create(
        self,
        name: str,
        theme_service: Optional["ThemeService"] = None,
        **kwargs: Any,
    ) -> Optional[BaseComponent]:
        component_class = self._components.get(name)
        if component_class:
            return component_class(theme_service=theme_service, **kwargs)
        logger.warning(f"Unknown component: {name}")
        return None

    def get(self, name: str) -> Optional[type]:
        return self._components.get(name)


def get_component_registry() -> ComponentRegistry:
    return ComponentRegistry()


def register_component(name: str):
    def decorator(cls: type) -> type:
        get_component_registry().register(name, cls)
        return cls

    return decorator


# ============================================================================
# Layout Helpers (unchanged)
# ============================================================================


def create_h_layout(
    *widgets: QWidget,
    spacing: int = 8,
    margins: tuple = (0, 0, 0, 0),
) -> QHBoxLayout:
    layout = QHBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    for widget in widgets:
        if widget:
            layout.addWidget(widget)
    return layout


def create_v_layout(
    *widgets: QWidget,
    spacing: int = 8,
    margins: tuple = (0, 0, 0, 0),
) -> QVBoxLayout:
    layout = QVBoxLayout()
    layout.setSpacing(spacing)
    layout.setContentsMargins(*margins)
    for widget in widgets:
        if widget:
            layout.addWidget(widget)
    return layout


# ============================================================================
# Exports
# ============================================================================


__all__ = [
    # Animation
    "AnimationDuration",
    "AnimationEasing",
    "AnimationMixin",
    "HoverEffectMixin",
    "RippleEffectMixin",
    # Loading
    "SkeletonLoader",
    "LoadingOverlay",
    "SpinnerWidget",
    # Lifecycle
    "ComponentState",
    "ComponentContext",
    "IComponent",
    # Mixins
    "ThemedComponentMixin",
    "StatefulViewMixin",
    "DisposableMixin",
    # Base
    "BaseComponent",
    # Themed
    "ThemedWidget",
    "ThemedFrame",
    "ThemedButton",
    "ThemedLabel",
    # Registry
    "ComponentRegistry",
    "get_component_registry",
    "register_component",
    # Helpers
    "create_h_layout",
    "create_v_layout",
]
