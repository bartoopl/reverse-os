"""
Returns service layer: orchestrates order fetch, rule evaluation,
label generation, and refund initiation.
All operations idempotent (Golden Rule #1).
All state changes via Return.transition_to() (Golden Rule #2).
All rule decisions logged (Golden Rule #3).
"""
from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models.return_model import Return, ReturnItem
from core.security.pii import encrypt, anonymize_payload
from core.security.return_token import verify_and_consume_token
from integrators.ecommerce.base import ecommerce_registry
from modules.rule_engine.engine import build_facts, rule_engine

log = structlog.get_logger(__name__)


class ReturnService:
    async def initiate_return(
        self,
        db: AsyncSession,
        *,
        platform: str,
        external_order_id: str,
        order_token: str,
        items: list[dict],         # [{order_item_id, quantity, reason, reason_detail}]
        return_method: str,
        customer_notes: str | None = None,
        idempotency_key: str | None = None,
    ) -> Return:
        """
        Full return initiation flow:
        1. Verify token & fetch order
        2. Upsert customer (PII vaulted)
        3. Create Return in 'pending' state
        4. Run rule engine
        5. Transition to decision state
        6. Audit log
        """
        idem_key = idempotency_key or self._build_idempotency_key(
            external_order_id, items
        )

        # Idempotency check (Golden Rule #1)
        existing = await db.execute(
            select(Return).where(Return.idempotency_key == idem_key)
        )
        if hit := existing.scalar_one_or_none():
            log.info("return.idempotent_hit", idempotency_key=idem_key, return_id=str(hit.id))
            return hit

        integrator = ecommerce_registry.get(platform)

        # Token already verified and consumed by the endpoint layer (returns.py).
        # We still need integrator.fetch_order — use token for Shopify API auth.
        remote_order = await integrator.fetch_order(external_order_id)

        # Upsert customer & vault PII
        customer = await self._upsert_customer(db, remote_order, platform)

        # Upsert order
        order = await self._upsert_order(db, remote_order, customer.id)

        # Create return
        ret = Return(
            order_id=order.id,
            customer_id=customer.id,
            status="draft",
            return_method=return_method,
            customer_notes=customer_notes,
            idempotency_key=idem_key,
            submitted_at=datetime.now(timezone.utc),
        )
        db.add(ret)
        await db.flush()  # Get ret.id without full commit

        # Attach return items
        for item_data in items:
            ri = ReturnItem(
                return_id=ret.id,
                order_item_id=item_data["order_item_id"],
                quantity_requested=item_data["quantity"],
                reason=item_data["reason"],
                reason_detail=item_data.get("reason_detail"),
                customer_condition=item_data.get("condition"),
            )
            db.add(ri)

        ret.transition_to("pending")
        await db.flush()

        # Rule engine evaluation
        facts = build_facts(ret, order, customer)
        engine_result = await rule_engine.evaluate(db, str(ret.id), facts)

        ret.rule_set_id = engine_result.matched_rule_id
        ret.rule_decision = engine_result.decision
        ret.rule_log = {
            "decision": engine_result.decision,
            "matched_rule": engine_result.matched_rule_name,
            "facts": anonymize_payload(engine_result.facts_snapshot),
            "trace": engine_result.log_entries,
        }

        # Transition based on rule decision
        decision_to_status = {
            "auto_approved": "approved",
            "keep_it": "keep_it",
            "require_inspection": "requires_inspection",
            "rejected": "rejected",
            "no_match": "requires_inspection",  # Default: human review
        }
        next_status = decision_to_status[engine_result.decision]
        ret.transition_to(next_status)

        await self._write_audit(db, ret, actor_type="system", action="return_created")

        log.info(
            "return.created",
            return_id=str(ret.id),
            rma=ret.rma_number,
            status=ret.status,
            decision=engine_result.decision,
        )
        return ret

    async def warehouse_inspect(
        self,
        db: AsyncSession,
        *,
        return_id: str,
        inspector_id: str,
        item_decisions: list[dict],   # [{return_item_id, decision, quantity_accepted, notes, photo_urls}]
    ) -> Return:
        """Process warehouse inspection results and transition return state."""
        ret = await db.get(Return, return_id)
        if not ret:
            raise ValueError(f"Return {return_id} not found")

        all_accepted = True
        any_accepted = False

        for decision in item_decisions:
            item = await db.get(ReturnItem, decision["return_item_id"])
            if not item or item.return_id != ret.id:
                raise ValueError("Return item not found or doesn't belong to this return")

            item.warehouse_decision = decision["decision"]
            item.quantity_accepted = decision.get("quantity_accepted", 0)
            item.warehouse_notes = decision.get("notes")
            item.inspection_photo_urls = decision.get("photo_urls", [])
            item.warehouse_condition = decision.get("condition")
            item.inspected_at = datetime.now(timezone.utc)
            item.inspected_by = inspector_id

            if decision["decision"] != "accept":
                all_accepted = False
            if decision["decision"] in ("accept", "partial_accept"):
                any_accepted = True

        if all_accepted:
            ret.transition_to("received")
        elif any_accepted:
            ret.transition_to("partial_received")
        else:
            ret.transition_to("rejected")

        await self._write_audit(db, ret, actor_type="user", actor_id=inspector_id, action="warehouse_inspection_submitted")
        return ret

    @staticmethod
    def _build_idempotency_key(order_id: str, items: list[dict]) -> str:
        item_sig = ",".join(
            f"{i['order_item_id']}:{i['quantity']}:{i['reason']}"
            for i in sorted(items, key=lambda x: x["order_item_id"])
        )
        raw = f"{order_id}|{item_sig}"
        return hashlib.sha256(raw.encode()).hexdigest()

    @staticmethod
    async def _upsert_customer(db: AsyncSession, order: any, platform: str):
        from core.models.customer_model import Customer
        from core.models.pii_vault_model import PIIVault

        existing = await db.execute(
            select(Customer).where(
                Customer.external_id == order.customer.external_id,
                Customer.platform == platform,
            )
        )
        customer = existing.scalar_one_or_none()
        if customer:
            return customer

        pii = PIIVault(
            email_encrypted=encrypt(order.customer.email),
            name_encrypted=encrypt(order.customer.name or "") if order.customer.name else None,
            phone_encrypted=encrypt(order.customer.phone or "") if order.customer.phone else None,
        )
        db.add(pii)
        await db.flush()

        customer = Customer(
            pii_id=pii.id,
            external_id=order.customer.external_id,
            platform=platform,
        )
        db.add(customer)
        await db.flush()
        return customer

    @staticmethod
    async def _upsert_order(db: AsyncSession, remote_order: any, customer_id: str):
        from core.models.order_model import Order, OrderItem

        existing = await db.execute(
            select(Order).where(
                Order.external_id == remote_order.external_id,
                Order.platform == remote_order.platform,
            )
        )
        order = existing.scalar_one_or_none()
        if order:
            return order

        order = Order(
            external_id=remote_order.external_id,
            platform=remote_order.platform,
            customer_id=customer_id,
            order_number=remote_order.order_number,
            ordered_at=datetime.fromisoformat(remote_order.ordered_at),
            currency=remote_order.currency,
            total_gross=remote_order.total_gross,
            total_net=remote_order.total_net,
            invoice_ref=remote_order.invoice_ref,
            platform_data=anonymize_payload(remote_order.raw),
        )
        db.add(order)
        await db.flush()

        for ri in remote_order.items:
            db.add(OrderItem(
                order_id=order.id,
                external_id=ri.external_id,
                sku=ri.sku,
                name=ri.name,
                variant=ri.variant,
                quantity=ri.quantity,
                unit_price_gross=ri.unit_price_gross,
                image_url=ri.image_url,
            ))

        return order

    @staticmethod
    async def _write_audit(db: AsyncSession, ret: Return, *, actor_type: str, actor_id: str | None = None, action: str) -> None:
        from core.models.audit_log_model import AuditLog
        db.add(AuditLog(
            entity_type="return",
            entity_id=str(ret.id),
            action=action,
            actor_type=actor_type,
            actor_id=actor_id,
            new_value={"status": ret.status, "rma": ret.rma_number},
        ))


return_service = ReturnService()
