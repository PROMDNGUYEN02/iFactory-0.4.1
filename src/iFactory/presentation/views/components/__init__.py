# File: presentation/views/components/__init__.py
"""
iFactory Component Library

Reusable, themed UI components for consistent design.
"""

# Base classes
from .base import (
    ThemedWidget,
    ThemedFrame,
    ThemedButton,
    ThemedLabel,
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

__all__ = [
    # Base
    "ThemedWidget",
    "ThemedFrame",
    "ThemedButton",
    "ThemedLabel",
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
]
