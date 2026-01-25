from abc import ABC, abstractmethod


class ISecurityService(ABC):
    @abstractmethod
    def verify_permission(self, user_id: str, permission: str) -> bool:
        pass
