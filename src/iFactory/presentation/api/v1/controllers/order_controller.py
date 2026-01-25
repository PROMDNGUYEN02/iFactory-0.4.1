from fastapi import APIRouter, Depends, status, Query
from typing import Optional

from src.application.dtos.order_dtos import CreateOrderRequestDTO, ApproveOrderRequestDTO
from src.application.use_cases.order.create_order_use_case import CreateOrderUseCase
from src.application.use_cases.order.approve_order_use_case import ApproveOrderUseCase
from src.application.use_cases.order.get_order_use_case import GetOrderUseCase

from src.infrastructure.dependency_injection import get_create_order_uc, get_approve_order_uc, get_get_order_uc
from src.presentation.api.dependencies.auth import get_current_user
from src.presentation.api.schemas.order import CreateOrderRequestSchema, OrderResponseSchema

router = APIRouter(prefix="/orders", tags=["Orders"])


@router.post("/", response_model=OrderResponseSchema, status_code=status.HTTP_201_CREATED)
async def create_order(request: CreateOrderRequestSchema, use_case: CreateOrderUseCase = Depends(get_create_order_uc)):
    app_request = CreateOrderRequestDTO(**request.dict())
    return use_case.execute(app_request)


@router.get("/{order_id}", response_model=OrderResponseSchema)
async def get_order(order_id: str, use_case: GetOrderUseCase = Depends(get_get_order_uc)):
    return use_case.execute(order_id)


@router.post("/{order_id}/approve", response_model=OrderResponseSchema)
async def approve_order(
    order_id: str,
    approved_by: Optional[str] = Query(None, description="Legacy query parameter for approval"),
    current_user: str = Depends(get_current_user),
    use_case: ApproveOrderUseCase = Depends(get_approve_order_uc),
):
    # Backward compatibility: use query param if provided, otherwise fallback to security context
    approver = approved_by if approved_by else current_user
    app_request = ApproveOrderRequestDTO(order_id=order_id, approved_by=approver)
    return use_case.execute(app_request)
