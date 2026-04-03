"""
Inbound webhooks from logistics providers.
Receives tracking events and transitions return states accordingly.
"""
import hashlib
import hmac

import structlog
from fastapi import APIRouter, BackgroundTasks, Header, HTTPException, Request, status
from sqlalchemy import select

from core.config import settings
from core.database.session import AsyncSessionLocal
from core.models.return_model import Return

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/inpost", status_code=status.HTTP_200_OK)
async def inpost_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_inpost_signature: str | None = Header(None),
) -> dict:
    body = await request.body()

    # Verify HMAC signature
    if x_inpost_signature and settings.INPOST_API_TOKEN:
        secret = settings.INPOST_API_TOKEN.get_secret_value().encode()
        expected = hmac.new(secret, body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, x_inpost_signature):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid signature")

    data = await request.json()
    background_tasks.add_task(_process_inpost_event, data)
    return {"received": True}


@router.post("/stripe", status_code=status.HTTP_200_OK)
async def stripe_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    stripe_signature: str | None = Header(None),
) -> dict:
    body = await request.body()

    if stripe_signature and settings.STRIPE_WEBHOOK_SECRET:
        import stripe as stripe_lib
        try:
            event = stripe_lib.Webhook.construct_event(
                body, stripe_signature, settings.STRIPE_WEBHOOK_SECRET.get_secret_value()
            )
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid Stripe signature")
        background_tasks.add_task(_process_stripe_event, event)

    return {"received": True}


async def _process_inpost_event(data: dict) -> None:
    tracking_number = data.get("tracking_number")
    raw_status = data.get("status")
    if not tracking_number or not raw_status:
        return

    # Map InPost statuses to return transitions
    transit_statuses = {"confirmed", "taken_by_courier", "adopted_at_source_branch",
                        "sent_from_source_branch", "adopted_at_sorting_center"}
    received_statuses = {"delivered", "ready_to_pickup"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Return).where(Return.tracking_number == tracking_number)
        )
        ret = result.scalar_one_or_none()
        if not ret:
            log.warning("webhook.inpost.return_not_found", tracking=tracking_number)
            return

        try:
            if raw_status in transit_statuses and ret.status == "label_generated":
                ret.transition_to("in_transit")
                log.info("webhook.inpost.transition", rma=ret.rma_number, status="in_transit")
            elif raw_status in received_statuses and ret.status == "in_transit":
                ret.transition_to("received")
                log.info("webhook.inpost.transition", rma=ret.rma_number, status="received")
        except ValueError as e:
            log.warning("webhook.inpost.invalid_transition", error=str(e), rma=ret.rma_number)

        await db.commit()


async def _process_stripe_event(event: dict) -> None:
    from core.models.refund_model import Refund
    from sqlalchemy import update

    event_type = event.get("type")
    if event_type not in ("charge.refunded", "refund.updated"):
        return

    refund_data = event.get("data", {}).get("object", {})
    provider_refund_id = refund_data.get("id")
    stripe_status = refund_data.get("status")

    if not provider_refund_id:
        return

    status_map = {"succeeded": "succeeded", "failed": "failed", "canceled": "failed"}
    new_status = status_map.get(stripe_status)
    if not new_status:
        return

    async with AsyncSessionLocal() as db:
        await db.execute(
            update(Refund)
            .where(Refund.provider_refund_id == provider_refund_id)
            .values(status=new_status)
        )
        await db.commit()
        log.info("webhook.stripe.refund_updated", refund_id=provider_refund_id, status=new_status)
