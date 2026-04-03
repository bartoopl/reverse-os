"""
Token redemption endpoint.
Called by Next.js Route Handler server-side — never directly by the browser.

Flow:
  1. Email link → GET /redeem (Next.js)
  2. Next.js Route Handler → POST /api/v1/auth/redeem (this endpoint)
  3. Backend validates token (non-consuming), creates Redis session
  4. Returns session_id to Next.js
  5. Next.js sets HttpOnly cookie, redirects browser to /return (clean URL)
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.security.session import consume_session, create_session, get_session

router = APIRouter(prefix="/auth", tags=["auth"])


class RedeemRequest(BaseModel):
    order_id: str
    platform: str
    token: str


class RedeemResponse(BaseModel):
    session_id: str
    order_id: str
    platform: str


class SessionResponse(BaseModel):
    order_id: str
    platform: str
    valid: bool


@router.post(
    "/redeem",
    response_model=RedeemResponse,
    summary="Exchange one-time token for a server session (called by Next.js server-side only)",
)
async def redeem_token(
    payload: RedeemRequest,
    db: AsyncSession = Depends(get_db),
) -> RedeemResponse:
    # Non-consuming peek — just verify the token is valid
    row = await db.execute(
        text("""
            SELECT 1 FROM return_tokens
            WHERE token=:t AND order_id=:o AND platform=:p
              AND used=false AND expires_at > NOW()
        """),
        {"t": payload.token, "o": payload.order_id, "p": payload.platform},
    )
    if not row.fetchone():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid, expired or already used token",
        )

    session_id = await create_session(payload.order_id, payload.platform, payload.token)
    return RedeemResponse(
        session_id=session_id,
        order_id=payload.order_id,
        platform=payload.platform,
    )


@router.get(
    "/session",
    response_model=SessionResponse,
    summary="Validate a session ID (called by Next.js proxy routes)",
)
async def validate_session(session_id: str) -> SessionResponse:
    data = await get_session(session_id)
    if not data:
        return SessionResponse(order_id="", platform="", valid=False)
    return SessionResponse(order_id=data["order_id"], platform=data["platform"], valid=True)


@router.delete(
    "/session",
    summary="Consume (invalidate) a session — called once at return submission",
)
async def consume_session_endpoint(session_id: str) -> dict:
    data = await consume_session(session_id)
    if not data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found or already used")
    return {"consumed": True, "order_id": data["order_id"], "token": data["token"]}
