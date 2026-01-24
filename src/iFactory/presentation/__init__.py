"""
Presentation Layer Package.

This layer constitutes the User Interface (UI) and user interaction logic.
It acts as the outermost shell of the Clean Architecture.

Responsibilities:
    - Controllers: Handle user input and coordinate with the Application Layer (Use Cases).
    - Views: Define the visual structure (Widgets, Windows, Layouts).
    - Adapters: Bridge the gap between asynchronous Application Services
                 and synchronous UI frameworks (e.g., Qt Signals/Slots).
    - Managers: Manage cross-cutting UI concerns such as Themes, Icons,
                and animations.

Architecture:
    This layer depends inwardly on the Application Layer but
    should not be depended upon by lower layers (Domain/Infrastructure).
"""

from .managers import IconConfig, IconManager, ThemeManager
from .adapters import AsyncExecutor, QtSignalAdapter

__all__ = [
    "ThemeManager",
    "IconManager",
    "IconConfig",
    "AsyncExecutor",
    "QtSignalAdapter",
]
