"""Admin rule engine management — full CRUD for rule sets."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.models.audit_log_model import AuditLog
from core.models.rule_set_model import RuleSet
from core.security.rbac import require_role, require_min_role

router = APIRouter(prefix="/admin/rules", tags=["admin-rules"])


class RuleSetOut(BaseModel):
    id: str
    name: str
    description: str | None
    priority: int
    is_active: bool
    platform: str | None
    conditions: dict
    actions: list
    version: int
    created_at: str


class RuleSetCreate(BaseModel):
    name: str
    description: str | None = None
    priority: int = 100
    platform: str | None = None
    conditions: dict
    actions: list


class RuleSetUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    priority: int | None = None
    is_active: bool | None = None
    conditions: dict | None = None
    actions: list | None = None


@router.get("/", response_model=list[RuleSetOut], dependencies=[Depends(require_min_role("warehouse"))])
async def list_rules(db: AsyncSession = Depends(get_db)) -> list[RuleSetOut]:
    result = await db.execute(select(RuleSet).order_by(RuleSet.priority))
    return [_to_out(r) for r in result.scalars()]


@router.post("/", response_model=RuleSetOut, dependencies=[Depends(require_role("admin"))])
async def create_rule(
    payload: RuleSetCreate,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RuleSetOut:
    rule = RuleSet(
        name=payload.name,
        description=payload.description,
        priority=payload.priority,
        platform=payload.platform,
        conditions=payload.conditions,
        actions=payload.actions,
        created_by=actor["sub"],
    )
    db.add(rule)
    await db.flush()
    db.add(AuditLog(
        entity_type="rule_set", entity_id=str(rule.id),
        action="rule_created", actor_id=actor["sub"], actor_type="user",
        new_value={"name": rule.name, "priority": rule.priority},
    ))
    return _to_out(rule)


@router.put("/{rule_id}", response_model=RuleSetOut, dependencies=[Depends(require_role("admin"))])
async def update_rule(
    rule_id: str,
    payload: RuleSetUpdate,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> RuleSetOut:
    rule = await db.get(RuleSet, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule set not found")

    old = {"name": rule.name, "priority": rule.priority, "is_active": rule.is_active}
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(rule, field, value)
    rule.version += 1

    db.add(AuditLog(
        entity_type="rule_set", entity_id=rule_id,
        action="rule_updated", actor_id=actor["sub"], actor_type="user",
        old_value=old, new_value=payload.model_dump(exclude_none=True),
    ))
    return _to_out(rule)


@router.delete("/{rule_id}", dependencies=[Depends(require_role("admin"))])
async def deactivate_rule(
    rule_id: str,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    rule = await db.get(RuleSet, rule_id)
    if not rule:
        raise HTTPException(status_code=404, detail="Rule set not found")
    rule.is_active = False
    db.add(AuditLog(
        entity_type="rule_set", entity_id=rule_id,
        action="rule_deactivated", actor_id=actor["sub"], actor_type="user",
        old_value={"is_active": True}, new_value={"is_active": False},
    ))
    return {"deactivated": True}


def _to_out(r: RuleSet) -> RuleSetOut:
    return RuleSetOut(
        id=str(r.id),
        name=r.name,
        description=r.description,
        priority=r.priority,
        is_active=r.is_active,
        platform=r.platform,
        conditions=r.conditions,
        actions=r.actions,
        version=r.version,
        created_at=r.created_at.isoformat() if r.created_at else "",
    )
