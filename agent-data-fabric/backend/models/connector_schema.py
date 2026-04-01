import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class ConnectorSchema(Base):
    __tablename__ = "connector_schemas"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_id = Column(UUID(as_uuid=True), ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False, default=1)
    schema_json = Column(JSONB, nullable=False, default={})
    discovered_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    is_current = Column(Boolean, nullable=False, default=True)
