"""
Sprint 3: Financial Loop
- Refund initiation (Stripe / PayU)
- Store credit / voucher generation
- eCommerce order status sync after resolution
"""
from __future__ import annotations

import hashlib
import secrets
import string
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.audit_log_model import AuditLog
from core.models.refund_model import Refund
from core.models.return_model import Return
from core.models.voucher_model import Voucher

log = structlog.get_logger(__name__)

VOUCHER_ALPHABET = string.ascii_uppercase + string.digits
VOUCHER_TTL_DAYS = 365


class FinancialService:

    # ── Refunds ───────────────────────────────────────────────────────────

    async def initiate_refund(
        self,
        db: AsyncSession,
        *,
        return_id: str,
        provider: str,
        original_payment_id: str,
        amount: Decimal,
        currency: str = "PLN",
        actor_id: str | None = None,
    ) -> Refund:
        """
        Create a Refund record and dispatch to Celery worker.
        Idempotent: calling twice with same return_id returns existing refund.
        """
        ret = await db.get(Return, return_id)
        if not ret:
            raise ValueError(f"Return {return_id} not found")
        if ret.status not in ("received", "partial_received", "keep_it", "approved"):
            raise ValueError(f"Cannot initiate refund from status: {ret.status!r}")

        # Idempotency key — deterministic from return + amount so retries are safe
        idem_key = hashlib.sha256(
            f"{return_id}:{provider}:{amount}:{currency}".encode()
        ).hexdigest()

        existing = await db.execute(select(Refund).where(Refund.idempotency_key == idem_key))
        if hit := existing.scalar_one_or_none():
            log.info("refund.idempotent_hit", return_id=return_id, refund_id=str(hit.id))
            return hit

        refund = Refund(
            return_id=return_id,
            idempotency_key=idem_key,
            provider=provider,
            amount=amount,
            currency=currency,
            status="pending",
            created_by=actor_id,
        )
        db.add(refund)
        await db.flush()

        ret.transition_to("refund_initiated")
        ret.approved_refund_amount = amount

        db.add(AuditLog(
            entity_type="return",
            entity_id=return_id,
            action="refund_initiated",
            actor_id=actor_id,
            actor_type="user" if actor_id else "system",
            new_value={"amount": str(amount), "provider": provider, "refund_id": str(refund.id)},
        ))

        # Dispatch async task — token already stored in DB before calling provider
        from workers.tasks import initiate_refund as refund_task
        refund_task.delay(
            return_id=return_id,
            amount=float(amount),
            currency=currency,
            provider=provider,
            original_payment_id=original_payment_id,
            idempotency_key=idem_key,
        )

        log.info("refund.dispatched", return_id=return_id, amount=str(amount), provider=provider)
        return refund

    # ── Store Credit / Vouchers ───────────────────────────────────────────

    async def issue_store_credit(
        self,
        db: AsyncSession,
        *,
        return_id: str,
        amount: Decimal,
        currency: str = "PLN",
        actor_id: str | None = None,
    ) -> Voucher:
        """Generate a unique voucher code for store credit."""
        ret = await db.get(Return, return_id)
        if not ret:
            raise ValueError(f"Return {return_id} not found")
        if ret.status not in ("received", "partial_received", "keep_it", "approved"):
            raise ValueError(f"Cannot issue credit from status: {ret.status!r}")

        # Check not already issued for this return
        existing = await db.execute(
            select(Voucher).where(Voucher.return_id == return_id, Voucher.status == "active")
        )
        if hit := existing.scalar_one_or_none():
            log.info("voucher.already_exists", return_id=return_id, code=hit.code)
            return hit

        code = self._generate_code()
        voucher = Voucher(
            code=code,
            return_id=return_id,
            amount=amount,
            currency=currency,
            status="active",
            expires_at=datetime.now(timezone.utc) + timedelta(days=VOUCHER_TTL_DAYS),
        )
        db.add(voucher)
        await db.flush()

        ret.transition_to("store_credit_issued")
        ret.approved_refund_amount = amount

        db.add(AuditLog(
            entity_type="return",
            entity_id=return_id,
            action="store_credit_issued",
            actor_id=actor_id,
            actor_type="user" if actor_id else "system",
            new_value={"code": code, "amount": str(amount)},
        ))

        log.info("voucher.issued", return_id=return_id, code=code, amount=str(amount))
        return voucher

    # ── eCommerce Sync ────────────────────────────────────────────────────

    async def sync_order_status(
        self,
        db: AsyncSession,
        *,
        return_id: str,
    ) -> None:
        """
        Push return resolution status back to eCommerce platform.
        Called after refunded / store_credit_issued / rejected / closed.
        """
        from core.models.order_model import Order
        from integrators.ecommerce.base import ecommerce_registry

        ret = await db.get(Return, return_id)
        if not ret:
            return

        order = await db.get(Order, ret.order_id)
        if not order:
            return

        status_map = {
            "refunded":             "refunded",
            "store_credit_issued":  "refunded",
            "rejected":             "return_rejected",
            "approved":             "return_approved",
            "closed":               "refunded",
        }
        platform_status = status_map.get(ret.status)
        if not platform_status:
            return

        try:
            integrator = ecommerce_registry.get(order.platform)
            await integrator.update_order_status(order.external_id, platform_status)
            log.info("order_sync.ok", order=order.external_id, platform=order.platform, status=platform_status)
        except Exception as e:
            # Non-fatal — log and continue. Retry via Celery beat if needed.
            log.warning("order_sync.failed", order=order.external_id, error=str(e))

    @staticmethod
    def _generate_code(length: int = 16) -> str:
        """XXXXX-XXXXX-XXXXX-X format, URL-safe, unambiguous characters."""
        alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I
        raw = "".join(secrets.choice(alphabet) for _ in range(length))
        return f"{raw[:5]}-{raw[5:10]}-{raw[10:15]}-{raw[15]}"


financial_service = FinancialService()
