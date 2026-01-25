from pydantic import BaseModel
from typing import Optional
from datetime import datetime

# API Schemas ensure we do not leak internal structures.


class CreateOrderRequestSchema(BaseModel):
    product_id: str
    quantity: int
    customer_id: str


class OrderResponseSchema(BaseModel):
    id: str
    product_id: str
    quantity: int
    status: str
    created_at: datetime
    approved_by: Optional[str] = None
