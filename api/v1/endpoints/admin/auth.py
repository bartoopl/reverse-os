"""Admin login — returns JWT."""
from fastapi import APIRouter, Depends, HTTPException, status
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.models.user_model import User
from core.security.jwt import create_access_token

router = APIRouter(prefix="/admin/auth", tags=["admin-auth"])
pwd = CryptContext(schemes=["bcrypt"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    name: str | None


class MeResponse(BaseModel):
    id: str
    email: str
    name: str | None
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    result = await db.execute(select(User).where(User.email == payload.email, User.is_active == True))
    user = result.scalar_one_or_none()

    if not user or not user.password_hash or not pwd.verify(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")

    token = create_access_token(str(user.id), user.role)
    return LoginResponse(access_token=token, role=user.role, name=user.name)
