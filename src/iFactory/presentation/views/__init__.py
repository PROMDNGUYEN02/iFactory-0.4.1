# File: presentation/views/__init__.py
"""
Views for MVVM Architecture.

Views are PASSIVE components that:
- Bind to ViewModel signals
- Delegate user actions to ViewModels
- Use ThemeService for styling
- Do NOT contain business logic
"""

from .main_window import MainWindow

__all__ = [
    "MainWindow",
]
