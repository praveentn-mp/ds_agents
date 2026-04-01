import uuid
from datetime import datetime
from sqlalchemy import Column, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class MCPPrompt(Base):
    __tablename__ = "mcp_prompts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)
    description = Column(Text)
    template = Column(Text, nullable=False)
    variables = Column(JSONB, nullable=False, default=[])
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
