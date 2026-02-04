# src/iFactory/presentation/views/components/base.py
"""
Enhanced Base Components System.

Features:
- Lifecycle hooks (mount, unmount, update)
- Slot-based content projection
- Event delegation
- Render optimization
- Theme integration
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

from PySide6.QtCore import QObject, QTimer, Signal, Slot
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

if TYPE_CHECKING:
    from ...services.theme_service import ThemeService, ThemeTokens

logger = logging.getLogger(__name__)

T = TypeVar("T")


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

    def on_mount(self) -> None:
        """Called when component is added to UI."""
        ...

    def on_unmount(self) -> None:
        """Called when component is removed from UI."""
        ...

    def on_update(self, props: Dict[str, Any]) -> None:
        """Called when component props change."""
        ...


# ============================================================================
# Base Component
# ============================================================================


class BaseComponent(QWidget):
    """
    Enhanced base class for all UI components.

    Features:
    - Lifecycle hooks (mount, unmount, update)
    - Theme integration
    - Render optimization (batch updates)
    - Event handling
    - Slot-based content projection

    Lifecycle:
    1. __init__() - Create widget
    2. on_mount() - Called when added to parent
    3. on_update() - Called when props change
    4. on_unmount() - Called when removed

    Usage:
        class MyButton(BaseComponent):
            clicked = Signal()

            def __init__(self, text: str, **kwargs):
                super().__init__(**kwargs)
                self._text = text
                self._button = QPushButton(text, self)
                self._button.clicked.connect(self.clicked)

            def _apply_theme(self) -> None:
                self._button.setStyleSheet(f'''
                    QPushButton {{
                        background: {self.tokens.primary};
                        color: white;
                    }}
                ''')
    """

    # Signals
    mounted = Signal()
    unmounted = Signal()
    updated = Signal(dict)
    error_occurred = Signal(str)

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
        self._props: Dict[str, Any] = {}

        # Render optimization
        self._pending_update = False
        self._update_timer: Optional[QTimer] = None
        self._batch_updates: Dict[str, Any] = {}

        # Slots for content projection
        self._slots: Dict[str, QWidget] = {}

        # Setup theme binding
        if self._theme_service:
            self._theme_service.themeChanged.connect(self._on_theme_changed_internal)

    # ========================================================================
    # Lifecycle
    # ========================================================================

    def showEvent(self, event) -> None:
        """Handle show event - trigger mount."""
        super().showEvent(event)
        if not self._is_mounted:
            self._mount()

    def hideEvent(self, event) -> None:
        """Handle hide event."""
        super().hideEvent(event)

    def closeEvent(self, event) -> None:
        """Handle close event - trigger unmount."""
        self._unmount()
        super().closeEvent(event)

    def _mount(self) -> None:
        """Internal mount handler."""
        if self._is_mounted:
            return

        self._state = ComponentState.MOUNTING
        try:
            self.on_mount()
            self._is_mounted = True
            self._state = ComponentState.MOUNTED
            self.mounted.emit()

            # Apply initial theme
            if self._theme_service:
                self._apply_theme()

        except Exception as e:
            self._state = ComponentState.ERROR
            logger.error(f"[{self.__class__.__name__}] Mount error: {e}")
            self.error_occurred.emit(str(e))

    def _unmount(self) -> None:
        """Internal unmount handler."""
        if not self._is_mounted:
            return

        self._state = ComponentState.UNMOUNTING
        try:
            self.on_unmount()
            self._is_mounted = False
            self._state = ComponentState.UNMOUNTED
            self.unmounted.emit()

            # Cleanup
            if self._update_timer:
                self._update_timer.stop()
                self._update_timer.deleteLater()
                self._update_timer = None

        except Exception as e:
            logger.error(f"[{self.__class__.__name__}] Unmount error: {e}")

    def on_mount(self) -> None:
        """
        Called when component is mounted.
        Override in subclasses for initialization logic.
        """
        pass

    def on_unmount(self) -> None:
        """
        Called when component is unmounted.
        Override in subclasses for cleanup logic.
        """
        pass

    def on_update(self, changed_props: Dict[str, Any]) -> None:
        """
        Called when props change.
        Override in subclasses to react to prop changes.
        """
        pass

    # ========================================================================
    # Props & Updates
    # ========================================================================

    def set_props(self, **props: Any) -> None:
        """Update component props with batching."""
        changed = {}
        for key, value in props.items():
            if key not in self._props or self._props[key] != value:
                changed[key] = value
                self._props[key] = value

        if changed:
            self._schedule_update(changed)

    def get_prop(self, key: str, default: Any = None) -> Any:
        """Get a prop value."""
        return self._props.get(key, default)

    def _schedule_update(self, changed: Dict[str, Any]) -> None:
        """Schedule batched update."""
        self._batch_updates.update(changed)

        if self._pending_update:
            return

        self._pending_update = True

        # Use timer for batching (16ms = ~60fps)
        if not self._update_timer:
            self._update_timer = QTimer(self)
            self._update_timer.setSingleShot(True)
            self._update_timer.timeout.connect(self._flush_updates)

        self._update_timer.start(16)

    def _flush_updates(self) -> None:
        """Flush batched updates."""
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
        """Force immediate update."""
        if self._update_timer:
            self._update_timer.stop()
        self._flush_updates()

    # ========================================================================
    # Theme
    # ========================================================================

    @Slot(str)
    def _on_theme_changed_internal(self, theme: str) -> None:
        """Handle theme change."""
        if self._is_mounted:
            self._apply_theme()

    def _apply_theme(self) -> None:
        """
        Apply current theme styles.
        Override in subclasses.
        """
        pass

    @property
    def tokens(self) -> Optional["ThemeTokens"]:
        """Get current theme tokens."""
        if self._theme_service:
            return self._theme_service.tokens
        return None

    @property
    def is_dark(self) -> bool:
        """Check if dark theme is active."""
        if self._theme_service:
            return self._theme_service.is_dark
        return False

    # ========================================================================
    # Slots (Content Projection)
    # ========================================================================

    def set_slot(self, name: str, widget: QWidget) -> None:
        """Set content for a named slot."""
        if name in self._slots:
            old_widget = self._slots[name]
            old_widget.setParent(None)
            old_widget.deleteLater()

        self._slots[name] = widget
        widget.setParent(self)
        self._on_slot_changed(name, widget)

    def get_slot(self, name: str) -> Optional[QWidget]:
        """Get content from a named slot."""
        return self._slots.get(name)

    def _on_slot_changed(self, name: str, widget: QWidget) -> None:
        """
        Called when slot content changes.
        Override to handle slot content positioning.
        """
        pass

    # ========================================================================
    # State
    # ========================================================================

    @property
    def component_state(self) -> ComponentState:
        """Get current lifecycle state."""
        return self._state

    @property
    def is_mounted(self) -> bool:
        """Check if component is mounted."""
        return self._is_mounted


# ============================================================================
# Themed Variants
# ============================================================================


class ThemedWidget(BaseComponent):
    """
    Base class for themed widgets.

    Simplified version that auto-applies theme.
    """

    def __init__(
        self,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(theme_service=theme_service, parent=parent)

    @abstractmethod
    def _apply_theme(self) -> None:
        """Apply current theme styles. Must override."""
        pass


class ThemedFrame(QFrame):
    """
    Themed frame with lifecycle hooks.

    Lighter weight than BaseComponent for simple containers.
    """

    def __init__(
        self,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._theme_service = theme_service
        self._is_themed = False

        self._theme_service.themeChanged.connect(self._on_theme_changed)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        if not self._is_themed:
            self._apply_theme()
            self._is_themed = True

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        if self._is_themed:
            self._apply_theme()

    def _apply_theme(self) -> None:
        """Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens

    @property
    def is_dark(self) -> bool:
        return self._theme_service.is_dark


class ThemedButton(QPushButton):
    """Themed button."""

    def __init__(
        self,
        text: str,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self._theme_service = theme_service
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens


class ThemedLabel(QLabel):
    """Themed label."""

    def __init__(
        self,
        text: str,
        theme_service: "ThemeService",
        parent: Optional[QWidget] = None,
    ):
        super().__init__(text, parent)
        self._theme_service = theme_service
        self._theme_service.themeChanged.connect(self._on_theme_changed)
        self._apply_theme()

    @Slot(str)
    def _on_theme_changed(self, theme: str) -> None:
        self._apply_theme()

    def _apply_theme(self) -> None:
        """Override in subclasses."""
        pass

    @property
    def tokens(self) -> "ThemeTokens":
        return self._theme_service.tokens


# ============================================================================
# Component Utilities
# ============================================================================


class ComponentRegistry:
    """
    Registry for component types.

    Allows dynamic component creation by name.
    """

    _instance: Optional["ComponentRegistry"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._components = {}
        return cls._instance

    def register(self, name: str, component_class: type) -> None:
        """Register a component class."""
        self._components[name] = component_class

    def create(
        self,
        name: str,
        theme_service: Optional["ThemeService"] = None,
        **kwargs: Any,
    ) -> Optional[BaseComponent]:
        """Create a component by name."""
        component_class = self._components.get(name)
        if component_class:
            return component_class(theme_service=theme_service, **kwargs)
        logger.warning(f"Unknown component: {name}")
        return None

    def get(self, name: str) -> Optional[type]:
        """Get component class by name."""
        return self._components.get(name)


def get_component_registry() -> ComponentRegistry:
    """Get singleton component registry."""
    return ComponentRegistry()


def register_component(name: str):
    """Decorator to register a component."""

    def decorator(cls: type) -> type:
        get_component_registry().register(name, cls)
        return cls

    return decorator


# ============================================================================
# Layout Helpers
# ============================================================================


def create_h_layout(
    *widgets: QWidget,
    spacing: int = 8,
    margins: tuple = (0, 0, 0, 0),
) -> QHBoxLayout:
    """Create horizontal layout with widgets."""
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
    """Create vertical layout with widgets."""
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
    # Lifecycle
    "ComponentState",
    "ComponentContext",
    "IComponent",
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
