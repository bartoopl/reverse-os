"""Background tasks: tracking polling, KSeF sync, refund status reconciliation."""
import asyncio

import structlog

from workers.celery_app import celery_app

log = structlog.get_logger(__name__)


def run_async(coro):
    """Run async coroutine from sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def poll_tracking_updates(self):
    """
    Poll logistics providers for tracking updates on in-transit returns.
    Transitions return status when package is delivered.
    """
    try:
        run_async(_do_poll_tracking())
    except Exception as exc:
        log.error("task.poll_tracking.failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=5, default_retry_delay=300)
def sync_ksef_references(self):
    """
    Poll ERP for KSeF correction reference numbers on finalized returns.
    Updates returns.ksef_reference when ERP has processed the correction.
    """
    try:
        run_async(_do_sync_ksef())
    except Exception as exc:
        log.error("task.sync_ksef.failed", error=str(exc))
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=120)
def initiate_refund(self, return_id: str, amount: float, currency: str,
                    provider: str, original_payment_id: str, idempotency_key: str):
    """
    Process a refund asynchronously. Idempotency key prevents double-refunds
    even if this task is retried.
    """
    try:
        run_async(_do_refund(return_id, amount, currency, provider,
                             original_payment_id, idempotency_key))
    except Exception as exc:
        log.error("task.refund.failed", return_id=return_id, error=str(exc))
        raise self.retry(exc=exc)


async def _do_poll_tracking():
    from sqlalchemy import select
    from core.database.session import AsyncSessionLocal
    from core.models.return_model import Return
    from integrators.logistics.base import logistics_registry

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Return).where(Return.status == "in_transit")
        )
        in_transit = result.scalars().all()

        for ret in in_transit:
            if not ret.tracking_number or not ret.logistics_provider:
                continue
            try:
                provider = logistics_registry.get(ret.logistics_provider)
                tracking = await provider.get_tracking_status(ret.tracking_number)
                if tracking.status == "received" and ret.status == "in_transit":
                    ret.transition_to("received")
                    log.info("task.tracking.received", rma=ret.rma_number)
            except Exception as e:
                log.warning("task.tracking.error", rma=ret.rma_number, error=str(e))

        await db.commit()


async def _do_sync_ksef():
    """
    For each finalized return without a ksef_reference:
    1. Build correction invoice payload
    2. POST to ERP webhook (URL from settings)
    3. ERP responds with {ksef_reference_number: "..."}  (or 202 Accepted for async)
    4. On 202: poll is retried next beat cycle; on 200: update immediately
    """
    from sqlalchemy import select, update
    from core.config import settings
    from core.database.session import AsyncSessionLocal
    from core.models.order_model import Order, OrderItem
    from core.models.return_model import Return, ReturnItem
    from modules.returns.ksef_export import ksef_exporter

    if not getattr(settings, "ERP_WEBHOOK_URL", None):
        log.info("task.ksef_sync.skipped", reason="ERP_WEBHOOK_URL not configured")
        return

    import httpx

    _SELLER = {
        "name": getattr(settings, "COMPANY_NAME", "REVERSE-OS"),
        "nip": getattr(settings, "COMPANY_NIP", "0000000000"),
        "address": getattr(settings, "COMPANY_ADDRESS", ""),
    }

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Return)
            .where(Return.status == "refunded")
            .where(Return.ksef_reference == None)  # noqa: E711
            .limit(50)
        )
        pending = result.scalars().all()

        async with httpx.AsyncClient(timeout=15) as client:
            for ret in pending:
                try:
                    order_r = await db.execute(select(Order).where(Order.id == ret.order_id))
                    order = order_r.scalar_one_or_none()
                    if not order:
                        continue

                    ri_r = await db.execute(select(ReturnItem).where(ReturnItem.return_id == ret.id))
                    return_items = ri_r.scalars().all()

                    oi_r = await db.execute(select(OrderItem).where(OrderItem.order_id == order.id))
                    order_items_map = {str(oi.id): oi for oi in oi_r.scalars().all()}

                    payload = ksef_exporter.build_correction(
                        return_obj=ret,
                        order=order,
                        return_items=return_items,
                        order_items_map=order_items_map,
                        seller=_SELLER,
                    )

                    resp = await client.post(
                        settings.ERP_WEBHOOK_URL,
                        json=payload,
                        headers={"X-Source": "reverseos"},
                    )

                    if resp.status_code == 200:
                        data = resp.json()
                        ksef_ref = data.get("ksef_reference_number") or data.get("ksef_ref")
                        if ksef_ref:
                            await db.execute(
                                update(Return)
                                .where(Return.id == ret.id)
                                .values(ksef_reference=ksef_ref)
                            )
                            log.info("task.ksef_sync.updated", rma=ret.rma_number, ref=ksef_ref)
                    elif resp.status_code == 202:
                        log.info("task.ksef_sync.accepted_async", rma=ret.rma_number)
                    else:
                        log.warning("task.ksef_sync.erp_error", rma=ret.rma_number, status=resp.status_code)

                except Exception as e:
                    log.warning("task.ksef_sync.item_error", rma=ret.rma_number, error=str(e))

        await db.commit()


async def _do_refund(return_id: str, amount: float, currency: str,
                     provider: str, original_payment_id: str, idempotency_key: str):
    from decimal import Decimal
    from sqlalchemy import select, update
    from core.database.session import AsyncSessionLocal
    from core.models.refund_model import Refund
    from core.models.return_model import Return
    from integrators.payments.base import payment_registry, RefundStatus

    async with AsyncSessionLocal() as db:
        # Idempotency: mark as processing before calling provider
        await db.execute(
            update(Refund)
            .where(Refund.idempotency_key == idempotency_key)
            .values(status="processing")
        )
        await db.commit()

        try:
            integrator = payment_registry.get(provider)
            result = await integrator.create_refund(
                original_payment_id=original_payment_id,
                amount=Decimal(str(amount)),
                currency=currency,
                idempotency_key=idempotency_key,
            )

            new_status = "succeeded" if result.status == RefundStatus.SUCCEEDED else "failed"
            await db.execute(
                update(Refund)
                .where(Refund.idempotency_key == idempotency_key)
                .values(
                    status=new_status,
                    provider_refund_id=result.provider_refund_id,
                    provider_response=result.raw,
                )
            )

            if new_status == "succeeded":
                ret_result = await db.execute(select(Return).where(Return.id == return_id))
                ret = ret_result.scalar_one_or_none()
                if ret:
                    ret.transition_to("refunded")

            await db.commit()
            log.info("task.refund.done", return_id=return_id, status=new_status)

        except Exception as e:
            await db.execute(
                update(Refund)
                .where(Refund.idempotency_key == idempotency_key)
                .values(status="failed", failure_reason=str(e))
            )
            await db.commit()
            raise
