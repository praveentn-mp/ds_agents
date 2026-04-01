import uuid
from datetime import datetime
from sqlalchemy import Column, Text, Integer, TIMESTAMP, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from backend.database import Base


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_id = Column(UUID(as_uuid=True), ForeignKey("connectors.id", ondelete="CASCADE"), nullable=False)
    status = Column(Text, nullable=False, default="pending")
    rows_synced = Column(Integer, default=0)
    error_message = Column(Text)
    started_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    completed_at = Column(TIMESTAMP(timezone=True))
