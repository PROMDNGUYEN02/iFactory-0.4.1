"""
Shared File/IO Utilities.

Contains logic for handling file paths, layouts, and file system access.
Used by Presentation (UI) and Application to load layouts/configs without
depending on Infrastructure.
"""

from __future__ import annotations
import json
import logging
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

__all__ = [
    "LayoutCache",
    "load_layout",
    "extract_codes_from_layout",
    "get_data_directory",
]


def get_data_directory() -> Path:
    """Get the data directory path."""
    candidates = [Path("data"), Path(__file__).parents[4] / "data", Path(__file__).parents[3] / "data", Path.home() / ".ifactory" / "data"]
    for path in candidates:
        if path.exists():
            return path
    default = Path("data")
    default.mkdir(parents=True, exist_ok=True)
    return default


class LayoutCache:
    """Thread-safe singleton cache for device layout."""

    _instance: Optional["LayoutCache"] = None
    _lock = Lock()
    __slots__ = ("_cache", "_mtime", "_path", "_codes")

    def __new__(cls) -> "LayoutCache":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._cache = {}
                    cls._instance._mtime = 0.0
                    cls._instance._path = None
                    cls._instance._codes = None
        return cls._instance

    def load(self, path: Optional[Path] = None) -> Dict[str, Any]:
        """Load layout with caching."""
        paths = [path, self._path, Path("data/device_positions.json"), get_data_directory() / "device_positions.json"]
        for p in paths:
            if p and p.exists():
                with self._lock:
                    mtime = p.stat().st_mtime
                    if mtime != self._mtime or not self._cache:
                        with p.open("r", encoding="utf-8") as f:
                            self._cache = json.load(f)
                        self._mtime = mtime
                        self._path = p
                        self._codes = None
                return self._cache
        return {}

    def get_codes(self) -> List[str]:
        """Extract device codes from layout."""
        if self._codes is not None:
            return self._codes
        if not self._cache:
            self.load()
        codes = set()
        for value in self._cache.values():
            if isinstance(value, dict):
                for dev in value.get("devices", []):
                    if isinstance(dev, dict) and "id" in dev:
                        codes.add(str(dev["id"]))
        self._codes = sorted(codes)
        return self._codes

    def invalidate(self) -> None:
        """Invalidate cache."""
        with self._lock:
            self._cache = {}
            self._mtime = 0.0
            self._codes = None


_layout_cache = LayoutCache()


def load_layout(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load device layout from JSON file."""
    return _layout_cache.load(path)


def extract_codes_from_layout(layout: Optional[Dict] = None) -> List[str]:
    """Extract device codes from layout dictionary."""
    if layout:
        codes = set()
        for value in layout.values():
            if isinstance(value, dict):
                for dev in value.get("devices", []):
                    if isinstance(dev, dict) and "id" in dev:
                        codes.add(str(dev["id"]))
        return sorted(codes)
    return _layout_cache.get_codes()
