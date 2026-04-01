import uuid
from datetime import datetime
from sqlalchemy import Column, Text, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False)
    role = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    message_metadata = Column("metadata", JSONB)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
