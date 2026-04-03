import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, JSON, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID

from core.database.session import Base


class Refund(Base):
    __tablename__ = "refunds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_id = Column(UUID(as_uuid=True), ForeignKey("returns.id"), nullable=False)
    idempotency_key = Column(String(255), unique=True, nullable=False)
    provider = Column(String(50), nullable=False)
    provider_refund_id = Column(String(255))
    amount = Column(Numeric(12, 2), nullable=False)
    currency = Column(String(3), nullable=False, default="PLN")
    status = Column(String(30), nullable=False, default="pending")
    provider_response = Column(JSON)
    failure_reason = Column(Text)
    initiated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    completed_at = Column(DateTime(timezone=True))
    created_by = Column(UUID(as_uuid=True))
