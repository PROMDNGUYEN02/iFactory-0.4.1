# File: presentation/controllers/shell_controller.py
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict

from PySide6.QtCore import QObject

from ..state.actions import (
    deselect_device,
    select_device,
    set_data_range,
    set_page,
    set_theme,
    toggle_right_panel,
    toggle_sidebar,
)

if TYPE_CHECKING:
    from ..state.store import Store

logger = logging.getLogger(__name__)


class ShellController(QObject):
    def __init__(self, store: "Store", config_path: Path = None, parent: QObject = None):
        super().__init__(parent)
        self._store = store
        self._config_path = config_path
        self._layout_cache: Dict[str, Any] = {}

    def toggle_theme(self) -> None:
        state = self._store.get_state()
        current = state.get("theme", "light")
        new_theme = "dark" if current == "light" else "light"
        self._store.dispatch(set_theme(new_theme))
        logger.info("Theme changed to: %s", new_theme)

    def navigate_to(self, page: str) -> None:
        self._store.dispatch(set_page(page))

    def toggle_sidebar_menu(self) -> None:
        self._store.dispatch(toggle_sidebar())

    def toggle_details_panel(self) -> None:
        self._store.dispatch(toggle_right_panel())

    def select_device(self, device_id: str) -> None:
        self._store.dispatch(select_device(device_id))

    def deselect_device(self) -> None:
        self._store.dispatch(deselect_device())

    def set_data_range(self, days: int) -> None:
        self._store.dispatch(set_data_range(days))

    def get_layout_config(self, area_key: str) -> Dict[str, Any]:
        if area_key in self._layout_cache:
            return self._layout_cache[area_key]

        if not self._config_path or not self._config_path.exists():
            logger.warning("Layout config not found: %s", self._config_path)
            return {}

        try:
            text = self._config_path.read_text(encoding="utf-8")
            data = json.loads(text)

            config = data.get(area_key, {})
            if not config:
                for key in data:
                    if area_key in key or key in area_key:
                        config = data[key]
                        break

            self._layout_cache[area_key] = config
            return config

        except Exception as e:
            logger.error("Failed to load layout config: %s", e)
            return {}
