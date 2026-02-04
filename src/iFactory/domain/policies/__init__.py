# src/iFactory/domain/policies/__init__.py
"""
Domain Policies.

Policies encapsulate business rules that govern domain behavior.
"""

from .transition_policy import StatusTransitionPolicy

__all__ = [
    "StatusTransitionPolicy",
]
