import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class LLMCall(Base):
    __tablename__ = "llm_calls"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(UUID(as_uuid=True), ForeignKey("messages.id", ondelete="CASCADE"))
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"))
    model = Column(Text, nullable=False)
    tokens_input = Column(Integer, nullable=False, default=0)
    tokens_output = Column(Integer, nullable=False, default=0)
    tokens_cache = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Integer, nullable=False, default=0)
    tool_calls = Column(JSONB)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
