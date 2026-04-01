import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class MCPTool(Base):
    __tablename__ = "mcp_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, nullable=False)
    description = Column(Text)
    input_schema = Column(JSONB, nullable=False, default={})
    source_type = Column(Text, nullable=False)
    source_id = Column(UUID(as_uuid=True))
    server_name = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
