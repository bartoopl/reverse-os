"""Admin financial endpoints — refund initiation, store credit, order sync."""
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.security.rbac import require_role
from modules.returns.financial import financial_service

router = APIRouter(prefix="/admin/financial", tags=["admin-financial"])


class RefundRequest(BaseModel):
    provider: str                  # 'stripe', 'payu'
    original_payment_id: str
    amount: float
    currency: str = "PLN"


class StoreCreditRequest(BaseModel):
    amount: float
    currency: str = "PLN"


class RefundOut(BaseModel):
    id: str
    status: str
    amount: float
    provider: str
    idempotency_key: str


class VoucherOut(BaseModel):
    id: str
    code: str
    amount: float
    currency: str
    status: str
    expires_at: str


@router.post("/{return_id}/refund", response_model=RefundOut)
async def initiate_refund(
    return_id: str,
    payload: RefundRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RefundOut:
    try:
        refund = await financial_service.initiate_refund(
            db,
            return_id=return_id,
            provider=payload.provider,
            original_payment_id=payload.original_payment_id,
            amount=Decimal(str(payload.amount)),
            currency=payload.currency,
            actor_id=actor["sub"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return RefundOut(
        id=str(refund.id),
        status=refund.status,
        amount=float(refund.amount),
        provider=refund.provider,
        idempotency_key=refund.idempotency_key,
    )


@router.post("/{return_id}/store-credit", response_model=VoucherOut)
async def issue_store_credit(
    return_id: str,
    payload: StoreCreditRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> VoucherOut:
    try:
        voucher = await financial_service.issue_store_credit(
            db,
            return_id=return_id,
            amount=Decimal(str(payload.amount)),
            currency=payload.currency,
            actor_id=actor["sub"],
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return VoucherOut(
        id=str(voucher.id),
        code=voucher.code,
        amount=float(voucher.amount),
        currency=voucher.currency,
        status=voucher.status,
        expires_at=voucher.expires_at.isoformat(),
    )


@router.post("/{return_id}/sync-order")
async def sync_order_status(
    return_id: str,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    await financial_service.sync_order_status(db, return_id=return_id)
    return {"synced": True}
