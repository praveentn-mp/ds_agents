import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Connector(Base):
    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)
    connector_type = Column(Text, nullable=False)
    description = Column(Text)
    config = Column(JSONB, nullable=False, default={})
    encrypted_credentials = Column(Text)
    sync_mode = Column(Text, nullable=False, default="live")
    sync_interval_seconds = Column(Integer, default=3600)
    last_synced_at = Column(TIMESTAMP(timezone=True))
    is_active = Column(Boolean, nullable=False, default=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
