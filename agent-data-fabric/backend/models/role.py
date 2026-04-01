import uuid
from datetime import datetime
from sqlalchemy import Column, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from backend.database import Base


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(Text, unique=True, nullable=False)
    permissions = Column(JSONB, nullable=False, default=[])
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
