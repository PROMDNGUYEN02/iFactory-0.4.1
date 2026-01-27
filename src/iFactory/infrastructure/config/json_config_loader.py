import json
import logging
from typing import Dict, Any
from pathlib import Path

logger = logging.getLogger(__name__)


class JsonConfigLoader:
    """
    Loads configuration from JSON files.
    """

    @staticmethod
    def load(file_path: Path) -> Dict[str, Any]:
        if not file_path.exists():
            logger.warning(f"Config file not found: {file_path}")
            return {}

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse config file {file_path}: {e}")
            return {}
        except Exception as e:
            logger.error(f"Error loading config file {file_path}: {e}")
            return {}
