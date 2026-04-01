import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class MCPServer(Base):
    __tablename__ = "mcp_servers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)
    image = Column(Text)
    container_id = Column(Text)
    sse_url = Column(Text)
    status = Column(Text, nullable=False, default="stopped")
    config = Column(JSONB, nullable=False, default={})
    encrypted_config = Column(Text)
    auto_register = Column(Boolean, nullable=False, default=True)
    is_enabled = Column(Boolean, nullable=False, default=True)
    registered_at = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
