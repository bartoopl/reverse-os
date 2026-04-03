import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, JSON, String
from sqlalchemy.dialects.postgresql import UUID

from core.database.session import Base


class RuleExecutionLog(Base):
    __tablename__ = "rule_execution_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    return_id = Column(UUID(as_uuid=True), ForeignKey("returns.id"), nullable=False)
    rule_set_id = Column(UUID(as_uuid=True))
    rule_set_name = Column(String(255))
    facts_snapshot = Column(JSON, nullable=False)
    conditions_snapshot = Column(JSON, nullable=False)
    matched = Column(Boolean, nullable=False)
    actions_taken = Column(JSON)
    executed_at = Column(DateTime(timezone=True), default=datetime.utcnow)
