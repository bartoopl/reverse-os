"""Admin user management — create, list, deactivate, change role."""
import bcrypt
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.models.audit_log_model import AuditLog
from core.models.user_model import User
from core.security.rbac import require_role

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

VALID_ROLES = ("admin", "warehouse", "viewer", "api_key")


class UserOut(BaseModel):
    id: str
    email: str
    name: str | None
    role: str
    is_active: bool
    last_login_at: str | None


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str | None = None
    role: str = "viewer"
    password: str


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None
    name: str | None = None


@router.get("/", response_model=list[UserOut], dependencies=[Depends(require_role("admin"))])
async def list_users(db: AsyncSession = Depends(get_db)) -> list[UserOut]:
    result = await db.execute(select(User).order_by(User.created_at))
    return [_to_out(u) for u in result.scalars()]


@router.post("/", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def create_user(
    payload: CreateUserRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Choose from: {VALID_ROLES}")

    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Email already exists")

    pw_hash = bcrypt.hashpw(payload.password.encode(), bcrypt.gensalt()).decode()
    user = User(email=payload.email, name=payload.name, role=payload.role, password_hash=pw_hash)
    db.add(user)
    await db.flush()

    db.add(AuditLog(
        entity_type="user", entity_id=str(user.id),
        action="user_created", actor_id=actor["sub"], actor_type="user",
        new_value={"email": payload.email, "role": payload.role},
    ))
    return _to_out(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    user_id: str,
    payload: UpdateUserRequest,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Guard: can't demote yourself
    if user_id == actor["sub"] and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    old = {"role": user.role, "is_active": user.is_active}
    if payload.role is not None:
        if payload.role not in VALID_ROLES:
            raise HTTPException(status_code=400, detail=f"Invalid role")
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.name is not None:
        user.name = payload.name

    db.add(AuditLog(
        entity_type="user", entity_id=user_id,
        action="user_updated", actor_id=actor["sub"], actor_type="user",
        old_value=old, new_value=payload.model_dump(exclude_none=True),
    ))
    return _to_out(user)


@router.post("/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    body: dict,
    actor: dict = Depends(require_role("admin")),
    db: AsyncSession = Depends(get_db),
) -> dict:
    user = await db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    new_password = body.get("password", "")
    if len(new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    user.password_hash = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
    db.add(AuditLog(
        entity_type="user", entity_id=user_id,
        action="password_reset", actor_id=actor["sub"], actor_type="user",
    ))
    return {"reset": True}


def _to_out(u: User) -> UserOut:
    return UserOut(
        id=str(u.id),
        email=u.email,
        name=u.name,
        role=u.role,
        is_active=u.is_active,
        last_login_at=u.last_login_at.isoformat() if u.last_login_at else None,
    )
