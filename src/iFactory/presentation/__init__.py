"""
Presentation Layer - iFactory
Clean Architecture Compliant.
"""

from .di.ui_container import UIContainer

# Export core architectural components
from .ui_state.store import Store
from .ui_state.actions import Action

# We no longer export a 'Selector' class,
# as selectors are now pure functions imported where needed.

__all__ = ["UIContainer", "Store", "Action"]
