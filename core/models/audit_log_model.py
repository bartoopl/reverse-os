import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, JSON, String, Text
from sqlalchemy.dialects.postgresql import INET, UUID

from core.database.session import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    action = Column(String(100), nullable=False)
    actor_id = Column(UUID(as_uuid=True))
    actor_type = Column(String(50))
    old_value = Column(JSON)
    new_value = Column(JSON)
    ip_address = Column(INET)
    user_agent = Column(Text)
    meta = Column(JSON)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
