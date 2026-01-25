from dataclasses import dataclass
from typing import Generic, TypeVar, List

T = TypeVar("T")


@dataclass(frozen=True)
class PaginatedResponseDTO(Generic[T]):
    items: List[T]
    total_count: int
    page: int
    size: int
