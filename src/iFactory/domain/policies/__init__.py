# src/iFactory/domain/policies/__init__.py
"""
Domain Policies.

Policies encapsulate business rules that don't naturally fit within
a single entity or value object.
"""

from .transition_policy import StatusTransitionPolicy

__all__ = ["StatusTransitionPolicy"]
