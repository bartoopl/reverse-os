"""Returns API endpoints - Customer Portal & Warehouse App."""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Header, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from sqlalchemy import func, select

from core.database.session import get_db
from core.licensing.license import LicenseManager
from core.models.return_model import Return
from core.security.return_token import verify_and_consume_token
from core.security.session import consume_session
from modules.returns.service import return_service

router = APIRouter(prefix="/returns", tags=["returns"])


class ReturnItemRequest(BaseModel):
    order_item_id: str
    quantity: int = Field(..., ge=1)
    reason: str
    reason_detail: str | None = None
    condition: str | None = None


class InitiateReturnRequest(BaseModel):
    platform: str
    external_order_id: str
    items: list[ReturnItemRequest] = Field(..., min_length=1)
    return_method: str
    customer_notes: str | None = None
    idempotency_key: str | None = None


class ReturnResponse(BaseModel):
    id: str
    rma_number: str
    status: str
    return_method: str | None
    rule_decision: str | None
    label_url: str | None
    tracking_number: str | None
    approved_refund_amount: float | None
    created_at: str


class WarehouseItemDecision(BaseModel):
    return_item_id: str
    decision: str
    quantity_accepted: int | None = None
    notes: str | None = None
    photo_urls: list[str] = []
    condition: str | None = None


class WarehouseInspectionRequest(BaseModel):
    item_decisions: list[WarehouseItemDecision] = Field(..., min_length=1)


@router.post(
    "/",
    response_model=ReturnResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Initiate a return (Customer Portal — requires X-Session-Id from BFF)",
)
async def initiate_return(
    payload: InitiateReturnRequest,
    x_session_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> ReturnResponse:
    if not x_session_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="X-Session-Id required")

    # Atomically consume session — prevents replay even under concurrent requests
    session = await consume_session(x_session_id)
    if (
        not session
        or session["order_id"] != payload.external_order_id
        or session["platform"] != payload.platform
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid or expired session")

    # Atomically consume the one-time token
    token_valid = await verify_and_consume_token(
        db, payload.external_order_id, payload.platform, session["token"]
    )
    if not token_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token already used or expired")

    # License gate: count this month's returns
    from datetime import date
    month_start = date.today().replace(day=1)
    count_result = await db.execute(
        select(func.count()).select_from(Return).where(Return.created_at >= month_start)
    )
    LicenseManager.check_return_limit(count_result.scalar_one())

    try:
        ret = await return_service.initiate_return(
            db,
            platform=payload.platform,
            external_order_id=payload.external_order_id,
            order_token=session["token"],  # passed for audit log only — already consumed above
            items=[i.model_dump() for i in payload.items],
            return_method=payload.return_method,
            customer_notes=payload.customer_notes,
            idempotency_key=payload.idempotency_key,
        )
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _to_response(ret)


@router.get(
    "/{rma_number}",
    response_model=ReturnResponse,
    summary="Get return status by RMA number",
)
async def get_return(
    rma_number: str,
    db: AsyncSession = Depends(get_db),
) -> ReturnResponse:
    from sqlalchemy import select
    from core.models.return_model import Return

    result = await db.execute(select(Return).where(Return.rma_number == rma_number))
    ret = result.scalar_one_or_none()
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    return _to_response(ret)


@router.post(
    "/{return_id}/inspect",
    response_model=ReturnResponse,
    summary="Submit warehouse inspection (Warehouse App)",
)
async def warehouse_inspect(
    return_id: str,
    payload: WarehouseInspectionRequest,
    x_inspector_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> ReturnResponse:
    if not x_inspector_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inspector ID required")

    try:
        ret = await return_service.warehouse_inspect(
            db,
            return_id=return_id,
            inspector_id=x_inspector_id,
            item_decisions=[d.model_dump() for d in payload.item_decisions],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return _to_response(ret)


def _to_response(ret) -> ReturnResponse:
    return ReturnResponse(
        id=str(ret.id),
        rma_number=ret.rma_number,
        status=ret.status,
        return_method=ret.return_method,
        rule_decision=ret.rule_decision,
        label_url=ret.label_url,
        tracking_number=ret.tracking_number,
        approved_refund_amount=float(ret.approved_refund_amount) if ret.approved_refund_amount else None,
        created_at=ret.created_at.isoformat() if ret.created_at else "",
    )
