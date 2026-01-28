"""
Infrastructure: Generic JSON Loader.
Pure I/O utility.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class JsonConfigLoader:
    """Safe JSON file reader."""

    @staticmethod
    def load(filepath: Path) -> Dict[str, Any]:
        if not filepath.exists() or not filepath.is_file():
            logger.warning(f"[JsonConfigLoader] File not found: {filepath}")
            return {}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"[JsonConfigLoader] Invalid JSON in {filepath}: {e}")
            return {}
        except Exception as e:
            logger.error(f"[JsonConfigLoader] Failed to read {filepath}: {e}")
            return {}
