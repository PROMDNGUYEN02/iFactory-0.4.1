# File: presentation/__init__.py
"""
Presentation Layer - MVVM Architecture.

This package contains all UI-related components following the MVVM pattern:

Structure:
├── di/                 # Dependency injection
│   └── ui_container.py # Main DI container
├── services/           # Infrastructure services
│   ├── theme_service.py    # Centralized theming (NEW)
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
│   └── shell/
│       ├── header.py
│       ├── sidebar.py
│       ├── right_panel.py
│       └── status_bar.py
└── resources/          # Assets and themes
    └── themes/
        ├── variables.json
        ├── base.qss
        └── manager.py  # Backward compat wrapper

Key Components:
- UIContainer: Main DI container for presentation layer
- ThemeService: Centralized theming (single source of truth)
- Store: Redux-like state management
- ViewModels: ShellViewModel, DeviceListViewModel, GanttChartViewModel
"""

from .di.ui_container import UIContainer
from .state.store import Store
from .state.actions import Action
from .services.theme_service import ThemeService, ThemeTokens, get_theme_service

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
]
