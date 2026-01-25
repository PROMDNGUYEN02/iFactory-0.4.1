from src.application.dtos.order_dtos import OrderDTO
from src.application.interfaces.repository import IRepository
from src.application.mappers.order_mapper import to_dto
from src.domain.entities.order import Order
from src.application.exceptions import ResourceNotFoundException


class GetOrderUseCase:
    def __init__(self, order_repository: IRepository[Order, str]):
        self._order_repo = order_repository

    def execute(self, order_id: str) -> OrderDTO:
        order = self._order_repo.get_by_id(order_id)
        if not order:
            raise ResourceNotFoundException("Order", order_id)

        return to_dto(order)
