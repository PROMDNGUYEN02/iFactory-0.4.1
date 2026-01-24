"""
Domain Services Package.

Contains stateless business logic that doesn't belong to a specific entity.
These services are pure domain logic with no infrastructure dependencies.
"""

from __future__ import annotations

from .status_normalization import StatusNormalizationService

__all__ = ["StatusNormalizationService"]
