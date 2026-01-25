# src/presentation/api/controllers/order_controller.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

# Import Application layer
from src.application.dtos.order_dtos import CreateOrderRequestDTO, ApproveOrderRequestDTO, OrderDTO
from src.application.exceptions import ResourceNotFoundException, UnauthorizedActionException, DomainConstraintViolationException
from src.application.use_cases.order.create_order_use_case import CreateOrderUseCase
from src.application.use_cases.order.approve_order_use_case import ApproveOrderUseCase
from src.application.use_cases.order.get_order_use_case import GetOrderUseCase

# Import DI container / dependencies (assumed setup in infrastructure)
from src.infrastructure.dependency_injection import get_create_order_uc, get_approve_order_uc, get_get_order_uc

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/", response_model=OrderDTO, status_code=status.HTTP_201_CREATED)
def create_order(request: CreateOrderRequestDTO, use_case: CreateOrderUseCase = Depends(get_create_order_uc)):
    try:
        return use_case.execute(request)
    except DomainConstraintViolationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{order_id}", response_model=OrderDTO)
def get_order(order_id: str, use_case: GetOrderUseCase = Depends(get_get_order_uc)):
    try:
        return use_case.execute(order_id)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{order_id}/approve", response_model=OrderDTO)
def approve_order(
    order_id: str, approved_by: str, use_case: ApproveOrderUseCase = Depends(get_approve_order_uc)  # In a real app, this comes from the auth token
):
    request = ApproveOrderRequestDTO(order_id=order_id, approved_by=approved_by)
    try:
        return use_case.execute(request)
    except ResourceNotFoundException as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except UnauthorizedActionException as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except DomainConstraintViolationException as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
