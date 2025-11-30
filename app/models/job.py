import enum

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"


class Job(Base):
    __tablename__ = "jobs"

    id = Column(Integer, primary_key=True, index=True)
    function_id = Column(Integer, ForeignKey("functions.id"), nullable=False)
    status = Column(Enum(JobStatus), default=JobStatus.PENDING)
    result = Column(Text, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())
    duration = Column(Integer, nullable=True)

    function = relationship("Function", back_populates="jobs")
