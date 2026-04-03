import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database.session import Base


class Customer(Base):
    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    pii_id = Column(UUID(as_uuid=True), ForeignKey("pii_vault.id"), nullable=False)
    external_id = Column(String(255))
    platform = Column(String(50))
    segment = Column(String(50), default="standard")
    total_orders = Column(Integer, default=0)
    total_returns = Column(Integer, default=0)
    return_rate = Column(Numeric(5, 4), default=0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
