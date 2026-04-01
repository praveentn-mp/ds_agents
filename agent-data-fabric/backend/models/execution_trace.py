import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class ExecutionTrace(Base):
    __tablename__ = "execution_traces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    trace_type = Column(Text, nullable=False)
    agent_name = Column(Text)
    tool_name = Column(Text)
    payload = Column(JSONB)
    status = Column(Text, nullable=False, default="running")
    duration_ms = Column(Integer)
    sequence = Column(Integer, nullable=False, default=0)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
