"""
JSON configuration loaders for Infrastructure and Presentation.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class DeviceConfigLoader:
    """
    Loads device position and layout configurations from JSON files.
    Used by the UI layer to render the factory floor.
    """

    @staticmethod
    def load_json(filepath: Path) -> Dict[str, Any]:
        if not filepath.exists():
            logger.warning(f"[DeviceConfigLoader] Config file not found: {filepath}")
            return {}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[DeviceConfigLoader] Failed to load JSON: {e}")
            return {}
