"""
Application Port: Configuration.
Interface for accessing application settings.
"""

from abc import ABC, abstractmethod
from typing import Any


class ISettingsManager(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> Any:
        pass

    @abstractmethod
    def set(self, key: str, value: Any, immediate: bool = False) -> None:
        pass

    @abstractmethod
    def save(self) -> None:
        pass
