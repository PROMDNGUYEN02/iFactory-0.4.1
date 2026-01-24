"""
Application Facades Package.

Provides simplified entry points for Presentation layer.
Facades orchestrate Use Cases and provide clean APIs for UI.
"""

from __future__ import annotations

from .device_facade import DeviceFacade

__all__ = ["DeviceFacade"]
