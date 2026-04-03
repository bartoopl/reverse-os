import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, LargeBinary
from sqlalchemy.dialects.postgresql import UUID

from core.database.session import Base


class PIIVault(Base):
    __tablename__ = "pii_vault"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email_encrypted = Column(LargeBinary, nullable=False)
    name_encrypted = Column(LargeBinary)
    phone_encrypted = Column(LargeBinary)
    address_encrypted = Column(LargeBinary)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow)
