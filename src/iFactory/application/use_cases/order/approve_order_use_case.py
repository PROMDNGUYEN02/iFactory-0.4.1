from iFactory.application.dtos.order_dtos import ApproveOrderRequestDTO, OrderDTO
from iFactory.application.interfaces.unit_of_work import IUnitOfWork
from iFactory.application.interfaces.repository import IRepository
from iFactory.application.interfaces.security import ISecurityService
from iFactory.application.mappers.order_mapper import to_dto
from iFactory.domain.entities.order import Order
from iFactory.domain.exceptions import DomainException
from iFactory.application.exceptions import ResourceNotFoundException, UnauthorizedActionException, DomainConstraintViolationException


class ApproveOrderUseCase:
    def __init__(self, uow: IUnitOfWork, order_repository: IRepository[Order, str], security_service: ISecurityService):
        self._uow = uow
        self._order_repo = order_repository
        self._security = security_service

    def execute(self, request: ApproveOrderRequestDTO) -> OrderDTO:
        if not self._security.verify_permission(request.approved_by, "APPROVE_ORDERS"):
            raise UnauthorizedActionException("User is not authorized to approve orders.")

        with self._uow:
            order = self._order_repo.get_by_id(request.order_id)
            if not order:
                raise ResourceNotFoundException("Order", request.order_id)

            try:
                order.approve()
                self._order_repo.save(order)
                self._uow.commit()
                return to_dto(order)
            except DomainException as e:
                raise DomainConstraintViolationException(str(e))
