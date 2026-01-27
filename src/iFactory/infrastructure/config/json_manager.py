import json
import logging
import aiofiles
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class JsonManager:
    """
    Async JSON file manager for persisting application state.
    """

    def __init__(self, file_path: Path):
        self._file_path = file_path

    async def load(self) -> Dict[str, Any]:
        if not self._file_path.exists():
            return {}
        try:
            async with aiofiles.open(self._file_path, mode="r", encoding="utf-8") as f:
                content = await f.read()
                return json.loads(content)
        except Exception as e:
            logger.error(f"Failed to load JSON {self._file_path}: {e}")
            return {}

    async def save(self, data: Dict[str, Any]) -> None:
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            async with aiofiles.open(self._file_path, mode="w", encoding="utf-8") as f:
                await f.write(json.dumps(data, indent=2))
        except Exception as e:
            logger.error(f"Failed to save JSON {self._file_path}: {e}")
