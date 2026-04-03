"""
Order lookup endpoint.
Accepts X-Session-Id header (from Next.js BFF proxy) — no token in URL.
Direct token fallback kept for internal/testing use only.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from core.database.session import get_db
from core.security.return_token import generate_token
from core.security.session import get_session
from integrators.ecommerce.base import OrderNotFound, ecommerce_registry

router = APIRouter(prefix="/orders", tags=["orders"])


class OrderItemOut(BaseModel):
    id: str
    sku: str
    name: str
    variant: str | None
    quantity: int
    unit_price_gross: float
    image_url: str | None


class OrderOut(BaseModel):
    external_id: str
    platform: str
    order_number: str
    ordered_at: str
    currency: str
    total_gross: float
    items: list[OrderItemOut]


@router.get(
    "/{external_order_id}",
    response_model=OrderOut,
    summary="Fetch order for return initiation",
)
async def get_order(
    external_order_id: str,
    platform: str = Query(...),
    x_session_id: Annotated[str | None, Header()] = None,
    db: AsyncSession = Depends(get_db),
) -> OrderOut:
    # Verify via session (normal flow from BFF)
    if x_session_id:
        session = await get_session(x_session_id)
        if (
            not session
            or session["order_id"] != external_order_id
            or session["platform"] != platform
        ):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid session")
    else:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Session-Id header required",
        )

    try:
        integrator = ecommerce_registry.get(platform)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Platform {platform!r} not supported")

    try:
        order = await integrator.fetch_order(external_order_id)
    except OrderNotFound:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    return OrderOut(
        external_id=order.external_id,
        platform=order.platform,
        order_number=order.order_number,
        ordered_at=order.ordered_at,
        currency=order.currency,
        total_gross=float(order.total_gross),
        items=[
            OrderItemOut(
                id=item.external_id,
                sku=item.sku,
                name=item.name,
                variant=item.variant,
                quantity=item.quantity,
                unit_price_gross=float(item.unit_price_gross),
                image_url=item.image_url,
            )
            for item in order.items
        ],
    )


class TokenRequest(BaseModel):
    order_id: str
    platform: str
    ttl_days: int = 7


class TokenResponse(BaseModel):
    token: str
    deep_link: str
    expires_in_days: int


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Generate one-time return token (merchant API — triggers email with deep link)",
)
async def create_return_token(
    payload: TokenRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    # TODO Sprint 4: require API key auth here
    token = await generate_token(db, payload.order_id, payload.platform, payload.ttl_days)
    # Deep link points to Next.js /redeem — token is redeemed server-side, never stays in URL
    deep_link = (
        f"http://localhost:3000/redeem"
        f"?orderId={payload.order_id}&platform={payload.platform}&token={token}"
    )
    return TokenResponse(token=token, deep_link=deep_link, expires_in_days=payload.ttl_days)
