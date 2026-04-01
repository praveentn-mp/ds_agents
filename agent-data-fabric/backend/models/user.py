import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Boolean, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from backend.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(Text, unique=True, nullable=False)
    hashed_password = Column(Text, nullable=False)
    full_name = Column(Text)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"))
    is_active = Column(Boolean, nullable=False, default=True)
    last_login = Column(TIMESTAMP(timezone=True))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)

    role = relationship("Role", lazy="joined")
