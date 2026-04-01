import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class ToolVersion(Base):
    __tablename__ = "tool_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tool_id = Column(UUID(as_uuid=True), ForeignKey("custom_tools.id", ondelete="CASCADE"), nullable=False)
    version = Column(Integer, nullable=False)
    code = Column(Text, nullable=False)
    input_schema = Column(JSONB, nullable=False, default={})
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
