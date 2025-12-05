import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    function_id = Column(UUID(as_uuid=True), ForeignKey("functions.id"), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    result = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    duration = Column(Integer, nullable=True)

    function = relationship("Function", back_populates="jobs")
