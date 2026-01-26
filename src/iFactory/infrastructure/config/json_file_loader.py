"""
Generic JSON configuration loader.
Pure I/O logic, no assumptions about the content's business or UI meaning.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger(__name__)


class JsonFileLoader:
    """Reads configuration files securely from the filesystem."""

    @staticmethod
    def load(filepath: Path) -> Dict[str, Any]:
        if not filepath.exists() or not filepath.is_file():
            logger.warning(f"[JsonFileLoader] File not found: {filepath}")
            return {}

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"[JsonFileLoader] Invalid JSON in {filepath}: {e}")
            return {}
        except Exception as e:
            logger.error(f"[JsonFileLoader] Failed to read {filepath}: {e}")
            return {}
