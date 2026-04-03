import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from core.database.session import Base


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_id = Column(String(255), nullable=False)
    platform = Column(String(50), nullable=False)
    customer_id = Column(UUID(as_uuid=True), ForeignKey("customers.id"), nullable=False)
    order_number = Column(String(100))
    ordered_at = Column(DateTime(timezone=True), nullable=False)
    currency = Column(String(3), nullable=False, default="PLN")
    total_gross = Column(Numeric(12, 2), nullable=False)
    total_net = Column(Numeric(12, 2))
    total_vat = Column(Numeric(12, 2))
    invoice_ref = Column(String(255))
    platform_data = Column(JSON)
    synced_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    items = relationship("OrderItem", back_populates="order", lazy="selectin")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False)
    external_id = Column(String(255))
    sku = Column(String(255), nullable=False)
    name = Column(String(500), nullable=False)
    variant = Column(String(255))
    quantity = Column(Integer, nullable=False)
    unit_price_gross = Column(Numeric(12, 2), nullable=False)
    unit_price_net = Column(Numeric(12, 2))
    vat_rate = Column(Numeric(5, 4))
    image_url = Column(String(1024))
    product_data = Column(JSON)

    order = relationship("Order", back_populates="items")
