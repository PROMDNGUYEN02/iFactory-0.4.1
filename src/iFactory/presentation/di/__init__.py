# File: presentation/di/__init__.py
"""
Dependency Injection Container for Presentation Layer.

UIContainer manages all presentation components with proper MVVM architecture:
- Initializes ThemeService first
- Creates ViewModels with proper dependencies
- Wires up signal connections
- Creates MainWindow with all dependencies
"""

from .container import UIContainer

__all__ = ["UIContainer"]
