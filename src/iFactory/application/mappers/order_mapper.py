from src.application.dtos.order_dtos import OrderDTO, OrderItemDTO
from src.domain.entities.order import Order
from typing import List


def to_dto(order: Order) -> OrderDTO:
    items_dto = [OrderItemDTO(product_id=item.product_id, quantity=item.quantity, price=item.price) for item in order.items]

    return OrderDTO(
        order_id=order.id,
        customer_id=order.customer_id,
        status=order.status.value,
        total_amount=order.total_amount,
        items=items_dto,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def to_dto_list(orders: List[Order]) -> List[OrderDTO]:
    return [to_dto(order) for order in orders]
