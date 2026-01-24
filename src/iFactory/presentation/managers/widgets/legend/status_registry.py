"""
StatusRegistry - Single source of truth for all status definitions.
"""

from __future__ import annotations
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Any
from .status_info import StatusInfo

__all__ = ["StatusRegistry", "get_status_registry"]
logger = logging.getLogger(__name__)


@dataclass
class StatusRegistry:
    """
    Central registry for all status definitions.
    Loads from JSON and provides lookup methods.
    """

    _by_db_code: Dict[str, StatusInfo] = field(default_factory=dict)
    _by_id: Dict[str, StatusInfo] = field(default_factory=dict)
    _by_alias: Dict[str, StatusInfo] = field(default_factory=dict)
    _all_statuses: List[StatusInfo] = field(default_factory=list)
    _unknown: Optional[StatusInfo] = None

    @classmethod
    def from_json(cls, path: Path) -> "StatusRegistry":
        registry = cls()
        try:
            if not path.exists():
                logger.warning(f"[StatusRegistry] Config not found: {path}")
                registry._load_defaults()
                return registry
            data = json.loads(path.read_text(encoding="utf-8"))
            if "status_registry" in data:
                statuses_data = data["status_registry"].get("statuses", [])
            elif "statuses" in data:
                statuses_data = data["statuses"]
            else:
                for key, value in data.items():
                    if isinstance(value, dict) and "statuses" in value:
                        statuses_data = value["statuses"]
                        break
                else:
                    statuses_data = []
            for item in statuses_data:
                status_info = cls._parse_status_item(item)
                registry._register(status_info, item.get("aliases", []))
            logger.info(f"[StatusRegistry] Loaded {len(registry._all_statuses)} statuses from {path}")
        except Exception as e:
            logger.error(f"[StatusRegistry] Failed to load: {e}")
            registry._load_defaults()
        return registry

    @classmethod
    def _parse_status_item(cls, item: Dict[str, Any]) -> StatusInfo:
        db_code = item.get("db_code") or item.get("code") or item.get("id", "0")
        return StatusInfo(
            db_code=str(db_code),
            id=item.get("id", "unknown"),
            label=item.get("label", "N/A"),
            color=item.get("color", "#9E9E9E"),
            color_dark=item.get("color_dark", item.get("color", "#BDBDBD")),
            emoji=item.get("emoji", "❓"),
            description=item.get("description", ""),
        )

    def _register(self, status_info: StatusInfo, aliases: List[str] = None) -> None:
        self._by_db_code[status_info.db_code] = status_info
        self._by_id[status_info.id] = status_info
        self._by_id[status_info.id.lower()] = status_info
        self._all_statuses.append(status_info)
        if aliases:
            for alias in aliases:
                self._by_alias[alias.lower()] = status_info
        if status_info.id in ("unknown", "n/a", "none"):
            self._unknown = status_info

    def _load_defaults(self) -> None:
        logger.info("[StatusRegistry] Loading default statuses")
        defaults = [
            {
                "db_code": "1",
                "id": "run",
                "label": "RUN",
                "color": "#3bb806",
                "color_dark": "#4ed812",
                "emoji": "🟢",
                "description": "Running",
            },
            {
                "db_code": "2",
                "id": "idle",
                "label": "IDLE",
                "color": "#c3c51b",
                "color_dark": "#d4d61f",
                "emoji": "🟡",
                "description": "Idle",
            },
            {
                "db_code": "3",
                "id": "stop",
                "label": "STOP",
                "color": "#F44336",
                "color_dark": "#EF5350",
                "emoji": "🔴",
                "description": "Stopped",
            },
            {
                "db_code": "4",
                "id": "pm",
                "label": "PM",
                "color": "#7f8174",
                "color_dark": "#969888",
                "emoji": "🛠️",
                "description": "Maintenance",
            },
            {
                "db_code": "5",
                "id": "bm",
                "label": "BM",
                "color": "#bd1e15",
                "color_dark": "#e0241a",
                "emoji": "⚠️",
                "description": "Breakdown",
            },
            {
                "db_code": "0",
                "id": "unknown",
                "label": "N/A",
                "color": "#9E9E9E",
                "color_dark": "#BDBDBD",
                "emoji": "❓",
                "description": "Unknown",
            },
        ]
        for item in defaults:
            status_info = self._parse_status_item(item)
            self._register(status_info, item.get("aliases", []))

    def get_by_code(self, db_code: str | int | None) -> StatusInfo:
        if db_code is None:
            return self.unknown
        return self._by_db_code.get(str(db_code).strip(), self.unknown)

    def get_by_id(self, status_id: str | None) -> StatusInfo:
        if status_id is None:
            return self.unknown
        return self._by_id.get(status_id.lower().strip(), self.unknown)

    def normalize(self, value: str | int | None) -> StatusInfo:
        if value is None:
            return self.unknown
        clean = str(value).strip().lower()
        if not clean:
            return self.unknown
        if clean in self._by_db_code:
            return self._by_db_code[clean]
        if clean in self._by_id:
            return self._by_id[clean]
        if clean in self._by_alias:
            return self._by_alias[clean]
        logger.debug(f"[StatusRegistry] Unknown status value: '{value}'")
        return self.unknown

    @property
    def unknown(self) -> StatusInfo:
        if self._unknown is None:
            self._unknown = StatusInfo("0", "unknown", "N/A", "#9E9E9E", "#BDBDBD", "❓", "Unknown status")
        return self._unknown

    @property
    def all_statuses(self) -> List[StatusInfo]:
        return self._all_statuses.copy()

    def get_color(self, value: str | int | None, theme: str = "light") -> str:
        return self.normalize(value).get_color(theme)

    def get_label(self, value: str | int | None) -> str:
        return self.normalize(value).label


_registry_instance: Optional[StatusRegistry] = None


def get_status_registry(config_path: Optional[Path] = None) -> StatusRegistry:
    global _registry_instance
    if _registry_instance is None:
        if config_path is None:
            candidates = [
                Path.cwd() / "data" / "legends.json",
                Path(__file__).resolve().parents[4] / "data" / "legends.json",
            ]
            config_path = next((p for p in candidates if p.exists()), candidates[0])
        _registry_instance = StatusRegistry.from_json(config_path)
    return _registry_instance


def reset_status_registry() -> None:
    global _registry_instance
    _registry_instance = None
