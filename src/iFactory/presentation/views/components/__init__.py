# File: presentation/views/components/__init__.py
"""
iFactory Component Library

Reusable, themed UI components for consistent design.
"""

# Base classes (includes animation, loading, and themed components)
from .base import (
    # Animation
    AnimationDuration,
    AnimationEasing,
    AnimationMixin,
    HoverEffectMixin,
    RippleEffectMixin,
    # Loading - from base.py
    SkeletonLoader,
    LoadingOverlay,
    SpinnerWidget,
    # Lifecycle
    ComponentState,
    ComponentContext,
    # Mixins
    ThemedComponentMixin,
    StatefulViewMixin,
    DisposableMixin,
    # Base
    BaseComponent,
    # Themed
    ThemedWidget,
    ThemedFrame,
    ThemedButton,
    ThemedLabel,
    # Registry
    ComponentRegistry,
    get_component_registry,
    register_component,
    # Helpers
    create_h_layout,
    create_v_layout,
)

# Buttons
from .buttons import (
    PrimaryButton,
    SecondaryButton,
    GhostButton,
    DangerButton,
    SuccessButton,
    IconButton,
    ToggleIconButton,
)

# Badges
from .badges import (
    StatusBadge,
    StatusDot,
    CountBadge,
    TextBadge,
)

# Cards
from .cards import (
    Card,
    ElevatedCard,
    StatCard,
    DeviceCard,
)

# Progress
from .progress import (
    AnimatedProgressBar,
    StatusProgressBar,
    CircularProgress,
)

# Labels
from .labels import (
    HeadingLabel,
    SecondaryLabel,
    MutedLabel,
    LinkLabel,
    MonoLabel,
    ErrorLabel,
    SuccessLabel,
)

# Inputs
from .inputs import (
    TextInput,
    SearchInput,
)

# Toast notifications
from .toast import (
    ToastWidget,
    ToastContainer,
)

# Extended loading components from loading.py (if different from base.py)
from .loading import (
    DeviceCardSkeleton,
    GanttRowSkeleton,
)

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
    "DeviceCardSkeleton",
    "GanttRowSkeleton",
    # Lifecycle
    "ComponentState",
    "ComponentContext",
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
    # Buttons
    "PrimaryButton",
    "SecondaryButton",
    "GhostButton",
    "DangerButton",
    "SuccessButton",
    "IconButton",
    "ToggleIconButton",
    # Badges
    "StatusBadge",
    "StatusDot",
    "CountBadge",
    "TextBadge",
    # Cards
    "Card",
    "ElevatedCard",
    "StatCard",
    "DeviceCard",
    # Progress
    "AnimatedProgressBar",
    "StatusProgressBar",
    "CircularProgress",
    # Labels
    "HeadingLabel",
    "SecondaryLabel",
    "MutedLabel",
    "LinkLabel",
    "MonoLabel",
    "ErrorLabel",
    "SuccessLabel",
    # Inputs
    "TextInput",
    "SearchInput",
    # Toast
    "ToastWidget",
    "ToastContainer",
]
