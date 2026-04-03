"""
Admin KSeF endpoints — correction invoice export.

GET /admin/ksef/queue          – returns needing correction invoice
GET /admin/returns/{id}/ksef-export?format=json|xml
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy import select, extract, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings
from core.database.session import get_db
from core.models.order_model import Order, OrderItem
from core.models.return_model import Return, ReturnItem
from core.security.rbac import require_role
from modules.returns.ksef_export import ksef_exporter

router = APIRouter(tags=["admin-ksef"])


@router.get(
    "/admin/ksef/queue",
    summary="Returns finalized — awaiting KSeF correction invoice",
)
async def ksef_queue(
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    result = await db.execute(
        select(Return)
        .where(Return.status == "refunded")
        .where(Return.ksef_reference == None)  # noqa: E711
        .order_by(Return.updated_at.desc())
        .limit(200)
    )
    returns = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "rma_number": r.rma_number,
            "status": r.status,
            "approved_refund_amount": float(r.approved_refund_amount) if r.approved_refund_amount else None,
            "ksef_reference": r.ksef_reference,
            "updated_at": r.updated_at.isoformat() if r.updated_at else None,
        }
        for r in returns
    ]


@router.get(
    "/admin/returns/{return_id}/ksef-export",
    summary="Export KSeF correction invoice for a finalized return",
)
async def ksef_export(
    return_id: str,
    format: str = Query("json", pattern="^(json|xml)$"),
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
):
    ret = await db.get(Return, return_id)
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    if ret.status not in ("refunded", "completed", "partially_refunded"):
        raise HTTPException(
            status_code=400,
            detail=f"KSeF export only available for finalized returns. Current status: {ret.status}",
        )

    # Load order
    order_result = await db.execute(select(Order).where(Order.id == ret.order_id))
    order = order_result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Load return items
    ri_result = await db.execute(select(ReturnItem).where(ReturnItem.return_id == ret.id))
    return_items = ri_result.scalars().all()

    # Load order items map
    oi_result = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
    order_items_map = {str(oi.id): oi for oi in oi_result.scalars().all()}

    seller = {
        "name": settings.COMPANY_NAME,
        "nip": settings.COMPANY_NIP,
        "address": settings.COMPANY_ADDRESS,
    }
    payload = ksef_exporter.build_correction(
        return_obj=ret,
        order=order,
        return_items=return_items,
        order_items_map=order_items_map,
        seller=seller,
    )

    if format == "xml":
        xml_str = ksef_exporter.to_xml(payload)
        return Response(
            content=xml_str,
            media_type="application/xml",
            headers={"Content-Disposition": f'attachment; filename="KOR-{ret.rma_number}.xml"'},
        )

    return payload
