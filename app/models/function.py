import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Runtime(str, enum.Enum):
    PYTHON = "python"
    NODEJS = "nodejs"


class ExecutionType(str, enum.Enum):
    SYNC = "sync"
    ASYNC = "async"


class Function(Base):
    __tablename__ = "functions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), unique=False, index=True, nullable=False)
    runtime = Column(Enum(Runtime), nullable=False)
    code = Column(Text, nullable=False)
    execution_type = Column(Enum(ExecutionType), nullable=False)
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    jobs = relationship("Job", back_populates="function")
    workspace = relationship("Workspace", back_populates="functions")
