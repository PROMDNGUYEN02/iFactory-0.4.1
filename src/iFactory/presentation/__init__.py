# File: presentation/__init__.py
"""
Presentation Layer - MVVM Architecture.

This package contains all UI-related components following the MVVM pattern:

Structure:
├── di/                 # Dependency injection
│   └── container.py    # Main UI container
├── services/           # Infrastructure services
│   ├── theme_service.py    # Centralized theming
│   ├── icon_service.py     # Centralized icon management
│   └── page_device_manager.py
├── state/              # Redux-like state management
│   ├── store.py
│   ├── actions.py
│   ├── reducers.py
│   └── selectors.py
├── viewmodels/         # MVVM ViewModels
│   ├── shell_viewmodel.py
│   ├── device_viewmodel.py
│   └── gantt_viewmodel.py
├── views/              # Passive UI components
│   ├── main_window.py
│   ├── components/     # Reusable UI components
│   └── shell/          # Shell views
└── resources/          # Assets and themes
    ├── themes/         # Design tokens & QSS
    └── icons/          # Icon registry & provider

Key Services:
- ThemeService: Centralized theming (single source of truth)
- IconService: Centralized icon management with caching
- Store: Redux-like state management
"""

from .di.container import UIContainer
from .state.store import Store
from .state.actions import Action
from .services.theme_service import (
    ThemeService,
    ThemeTokens,
    get_theme_service,
    create_theme_service,
)
from .services.icon_service import (
    IconService,
    IconSize,
    get_icon_service,
    create_icon_service,
)

__all__ = [
    # DI Container
    "UIContainer",
    # State Management
    "Store",
    "Action",
    # Theme Service
    "ThemeService",
    "ThemeTokens",
    "get_theme_service",
    "create_theme_service",
    # Icon Service
    "IconService",
    "IconSize",
    "get_icon_service",
    "create_icon_service",
]
