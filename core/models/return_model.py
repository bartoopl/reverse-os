"""
SQLAlchemy ORM models for the returns domain.
State machine transitions enforced at this layer (Golden Rule #2).
"""
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, Column, DateTime, Enum, ForeignKey,
    Integer, JSON, Numeric, String, Text, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database.session import Base

# Mirrors return_status_transitions table - source of truth is DB, this is app-layer guard
VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft":               {"pending", "cancelled"},
    "pending":             {"requires_inspection", "approved", "rejected", "keep_it"},
    "requires_inspection": {"approved", "rejected", "partial_received"},
    "approved":            {"label_generated", "keep_it"},
    "label_generated":     {"in_transit", "cancelled"},
    "in_transit":          {"received", "partial_received"},
    "received":            {"refund_initiated", "store_credit_issued"},
    "partial_received":    {"refund_initiated", "store_credit_issued"},
    "keep_it":             {"refund_initiated"},
    "refund_initiated":    {"refunded", "store_credit_issued"},
    "refunded":            {"closed"},
    "store_credit_issued": {"closed"},
    "rejected":            {"closed"},
    "cancelled":           {"closed"},
    "closed":              set(),
}


class Return(Base):
    __tablename__ = "returns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rma_number = Column(String(50), unique=True, nullable=False)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    status = Column(String(30), nullable=False, default="draft")
    return_method = Column(String(30))
    requested_refund_amount = Column(Numeric(12, 2))
    approved_refund_amount = Column(Numeric(12, 2))
    refund_type = Column(String(50))
    label_url = Column(String(1024))
    tracking_number = Column(String(255))
    logistics_provider = Column(String(50))
    logistics_data = Column(JSON)
    rule_set_id = Column(UUID(as_uuid=True))
    rule_decision = Column(String(50))
    rule_log = Column(JSON)
    ksef_reference = Column(String(255))
    erp_sync_at = Column(DateTime(timezone=True))
    customer_notes = Column(Text)
    internal_notes = Column(Text)
    submitted_at = Column(DateTime(timezone=True))
    resolved_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    idempotency_key = Column(String(255), unique=True)

    items = relationship("ReturnItem", back_populates="return_", cascade="all, delete-orphan")

    def transition_to(self, new_status: str) -> None:
        """
        Enforce state machine (Golden Rule #2).
        Raises ValueError on illegal transitions.
        """
        allowed = VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Illegal return transition: {self.status!r} -> {new_status!r}. "
                f"Allowed from {self.status!r}: {allowed or '{terminal state}'}"
            )
        self.status = new_status
        self.updated_at = datetime.utcnow()
        if new_status in {"refunded", "store_credit_issued", "rejected", "closed"}:
            self.resolved_at = datetime.utcnow()


class ReturnItem(Base):
    __tablename__ = "return_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_id = Column(UUID(as_uuid=True), ForeignKey("returns.id", ondelete="CASCADE"))
    order_item_id = Column(UUID(as_uuid=True), ForeignKey("order_items.id"))
    quantity_requested = Column(Integer, nullable=False)
    quantity_accepted = Column(Integer)
    reason = Column(String(50), nullable=False)
    reason_detail = Column(Text)
    customer_condition = Column(String(30))
    warehouse_decision = Column(String(30))
    warehouse_condition = Column(String(30))
    warehouse_notes = Column(Text)
    inspection_photo_urls = Column(JSON)
    inspected_at = Column(DateTime(timezone=True))
    inspected_by = Column(UUID(as_uuid=True))
    refund_amount = Column(Numeric(12, 2))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    return_ = relationship("Return", back_populates="items")
