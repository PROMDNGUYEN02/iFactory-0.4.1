from iFactory.application.dtos.order_dtos import CreateOrderRequestDTO, OrderDTO
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.repository import IRepository
from iFactory.application.mappers.order_mapper import to_dto
from iFactory.domain.entities.order import Order, OrderItem
from iFactory.domain.exceptions import DomainException
from iFactory.application.exceptions import DomainConstraintViolationException


class CreateOrderUseCase:
    def __init__(self, uow: IUnitOfWork, order_repository: IRepository[Order, str]):
        self._uow = uow
        self._order_repo = order_repository

    def execute(self, request: CreateOrderRequestDTO) -> OrderDTO:
        try:
            items = [OrderItem(product_id=i.product_id, quantity=i.quantity, price=i.price) for i in request.items]

            order = Order.create(customer_id=request.customer_id, items=items)

            with self._uow:
                self._order_repo.save(order)
                self._uow.commit()

            return to_dto(order)
        except DomainException as e:
            raise DomainConstraintViolationException(str(e))
