from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass(frozen=True)
class OrderItemDTO:
    product_id: str
    quantity: int
    price: float


@dataclass(frozen=True)
class OrderDTO:
    order_id: str
    customer_id: str
    status: str
    total_amount: float
    items: List[OrderItemDTO]
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class CreateOrderRequestDTO:
    customer_id: str
    items: List[OrderItemDTO]


@dataclass(frozen=True)
class ApproveOrderRequestDTO:
    order_id: str
    approved_by: str
