"""Admin returns management — list, detail, manual status override."""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.models.audit_log_model import AuditLog
from core.models.return_model import Return, ReturnItem, VALID_TRANSITIONS
from core.models.rule_execution_log_model import RuleExecutionLog
from core.security.rbac import require_role, require_min_role

router = APIRouter(prefix="/admin/returns", tags=["admin-returns"])


class ReturnListItem(BaseModel):
    id: str
    rma_number: str
    status: str
    platform: str | None
    rule_decision: str | None
    return_method: str | None
    approved_refund_amount: float | None
    created_at: str
    submitted_at: str | None


class ReturnListResponse(BaseModel):
    items: list[ReturnListItem]
    total: int
    page: int
    page_size: int


class ReturnDetail(BaseModel):
    id: str
    rma_number: str
    status: str
    return_method: str | None
    rule_decision: str | None
    rule_log: dict | None
    approved_refund_amount: float | None
    requested_refund_amount: float | None
    label_url: str | None
    tracking_number: str | None
    logistics_provider: str | None
    ksef_reference: str | None
    customer_notes: str | None
    internal_notes: str | None
    created_at: str
    submitted_at: str | None
    resolved_at: str | None
    allowed_transitions: list[str]
    items: list[dict]
    rule_log_entries: list[dict]
    audit_trail: list[dict]


class StatusOverrideRequest(BaseModel):
    new_status: str
    reason: str


class NotesRequest(BaseModel):
    internal_notes: str


@router.get("/", response_model=ReturnListResponse, dependencies=[Depends(require_min_role("warehouse"))])
async def list_returns(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    status_filter: str | None = Query(None, alias="status"),
    platform: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> ReturnListResponse:
    from core.models.order_model import Order

    q = select(Return, Order.platform).join(Order, Return.order_id == Order.id, isouter=True)
    if status_filter:
        q = q.where(Return.status == status_filter)
    if platform:
        q = q.where(Order.platform == platform)

    total_q = select(func.count()).select_from(q.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    q = q.order_by(Return.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).all()

    items = [
        ReturnListItem(
            id=str(ret.id),
            rma_number=ret.rma_number,
            status=ret.status,
            platform=plat,
            rule_decision=ret.rule_decision,
            return_method=ret.return_method,
            approved_refund_amount=float(ret.approved_refund_amount) if ret.approved_refund_amount else None,
            created_at=ret.created_at.isoformat() if ret.created_at else "",
            submitted_at=ret.submitted_at.isoformat() if ret.submitted_at else None,
        )
        for ret, plat in rows
    ]
    return ReturnListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{return_id}", response_model=ReturnDetail, dependencies=[Depends(require_min_role("warehouse"))])
async def get_return_detail(return_id: str, db: AsyncSession = Depends(get_db)) -> ReturnDetail:
    ret = await db.get(Return, return_id)
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    items_result = await db.execute(select(ReturnItem).where(ReturnItem.return_id == return_id))
    items = [
        {
            "id": str(i.id),
            "order_item_id": str(i.order_item_id),
            "quantity_requested": i.quantity_requested,
            "quantity_accepted": i.quantity_accepted,
            "reason": i.reason,
            "reason_detail": i.reason_detail,
            "customer_condition": i.customer_condition,
            "warehouse_decision": i.warehouse_decision,
            "refund_amount": float(i.refund_amount) if i.refund_amount else None,
        }
        for i in items_result.scalars()
    ]

    rule_logs_result = await db.execute(
        select(RuleExecutionLog)
        .where(RuleExecutionLog.return_id == return_id)
        .order_by(RuleExecutionLog.executed_at)
    )
    rule_log_entries = [
        {
            "rule_name": r.rule_set_name,
            "matched": r.matched,
            "executed_at": r.executed_at.isoformat() if r.executed_at else "",
            "actions_taken": r.actions_taken,
        }
        for r in rule_logs_result.scalars()
    ]

    audit_result = await db.execute(
        select(AuditLog)
        .where(AuditLog.entity_id == return_id)
        .order_by(AuditLog.created_at.desc())
        .limit(50)
    )
    audit_trail = [
        {
            "action": a.action,
            "actor_type": a.actor_type,
            "old_value": a.old_value,
            "new_value": a.new_value,
            "created_at": a.created_at.isoformat() if a.created_at else "",
        }
        for a in audit_result.scalars()
    ]

    return ReturnDetail(
        id=str(ret.id),
        rma_number=ret.rma_number,
        status=ret.status,
        return_method=ret.return_method,
        rule_decision=ret.rule_decision,
        rule_log=ret.rule_log,
        approved_refund_amount=float(ret.approved_refund_amount) if ret.approved_refund_amount else None,
        requested_refund_amount=float(ret.requested_refund_amount) if ret.requested_refund_amount else None,
        label_url=ret.label_url,
        tracking_number=ret.tracking_number,
        logistics_provider=ret.logistics_provider,
        ksef_reference=ret.ksef_reference,
        customer_notes=ret.customer_notes,
        internal_notes=ret.internal_notes,
        created_at=ret.created_at.isoformat() if ret.created_at else "",
        submitted_at=ret.submitted_at.isoformat() if ret.submitted_at else None,
        resolved_at=ret.resolved_at.isoformat() if ret.resolved_at else None,
        allowed_transitions=list(VALID_TRANSITIONS.get(ret.status, set())),
        items=items,
        rule_log_entries=rule_log_entries,
        audit_trail=audit_trail,
    )


@router.patch("/{return_id}/status", dependencies=[Depends(require_role("admin"))])
async def override_status(
    return_id: str,
    payload: StatusOverrideRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    ret = await db.get(Return, return_id)
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")

    old_status = ret.status
    try:
        ret.transition_to(payload.new_status)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    db.add(AuditLog(
        entity_type="return",
        entity_id=return_id,
        action="manual_status_override",
        actor_id=actor["sub"],
        actor_type="user",
        old_value={"status": old_status},
        new_value={"status": payload.new_status, "reason": payload.reason},
    ))
    return {"status": ret.status}


@router.patch("/{return_id}/notes", dependencies=[Depends(require_min_role("warehouse"))])
async def update_notes(
    return_id: str,
    payload: NotesRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    ret = await db.get(Return, return_id)
    if not ret:
        raise HTTPException(status_code=404, detail="Return not found")
    ret.internal_notes = payload.internal_notes
    return {"updated": True}
