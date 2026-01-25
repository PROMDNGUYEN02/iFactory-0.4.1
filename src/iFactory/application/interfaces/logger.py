from abc import ABC, abstractmethod


class ILogger(ABC):
    @abstractmethod
    def info(self, message: str) -> None:
        pass

    @abstractmethod
    def error(self, message: str) -> None:
        pass

    @abstractmethod
    def warning(self, message: str) -> None:
        pass
