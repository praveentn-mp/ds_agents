import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class CustomTool(Base):
    __tablename__ = "custom_tools"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)
    description = Column(Text)
    code = Column(Text, nullable=False)
    input_schema = Column(JSONB, nullable=False, default={})
    current_version = Column(Integer, nullable=False, default=1)
    is_active = Column(Boolean, nullable=False, default=True)
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
