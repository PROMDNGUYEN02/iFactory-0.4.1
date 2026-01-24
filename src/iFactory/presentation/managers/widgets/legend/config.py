from __future__ import annotations
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pathlib import Path

__all__ = ["LegendConfig", "find_legend_config_path", "load_legend_config"]
logger = logging.getLogger(__name__)


def find_legend_config_path() -> Optional[str]:
    candidates = [
        Path.cwd() / "data" / "legends.json",
        Path(__file__).resolve().parents[4] / "data" / "legends.json",
    ]
    for path in candidates:
        if path.exists():
            return str(path)
    return None


def load_legend_config(path: Optional[str] = None) -> Dict[str, Any]:
    import json

    config_path = path or find_legend_config_path()
    try:
        if config_path:
            p = Path(config_path)
            if p.exists():
                return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error(f"Failed to load legend config: {e}")
    return {}


@dataclass
class LegendConfig:
    title: str = "EQ Status"
    title_bg: str = "#939892"
    text_color: str = "#333333"
    text_color_dark: str = "#ffffff"
    base_box_width: int = 45
    base_box_height: int = 16
    base_spacing: int = 5
    base_title_width: int = 50
    base_font_size: int = 10
    base_title_font_size: int = 9
    ref_width: int = 600
    ref_height: int = 40
    min_scale: float = 0.5
    max_scale: float = 1.5
    statuses: List["StatusInfo"] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LegendConfig":
        return cls(
            title=data.get("title", "EQ Status"),
            title_bg=data.get("title_bg", "#939892"),
            text_color=data.get("text_color", "#333333"),
            text_color_dark=data.get("text_color_dark", "#ffffff"),
            base_box_width=data.get("base_box_width", 45),
            base_box_height=data.get("base_box_height", 16),
            base_spacing=data.get("base_spacing", 5),
            base_title_width=data.get("base_title_width", 50),
            base_font_size=data.get("base_font_size", 10),
            base_title_font_size=data.get("base_title_font_size", 9),
            ref_width=data.get("ref_width", 600),
            ref_height=data.get("ref_height", 40),
            min_scale=data.get("min_scale", 0.5),
            max_scale=data.get("max_scale", 1.5),
            statuses=[],
        )

    @classmethod
    def default(cls) -> "LegendConfig":
        return cls()

    def get_text_color(self, theme: str) -> str:
        return self.text_color_dark if theme == "dark" else self.text_color
