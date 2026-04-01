import uuid
from datetime import datetime
from sqlalchemy import Column, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class MCPResource(Base):
    __tablename__ = "mcp_resources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    uri = Column(Text, unique=True, nullable=False)
    name = Column(Text, nullable=False)
    description = Column(Text)
    resource_type = Column(Text, nullable=False)
    source_type = Column(Text, nullable=False)
    source_id = Column(UUID(as_uuid=True))
    mime_type = Column(Text)
    schema_json = Column(JSONB)
    last_updated = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
