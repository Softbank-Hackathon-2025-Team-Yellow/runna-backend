import enum
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text
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
    """
    Function 모델

    각 Function은 고유한 UUID를 가지며, Workspace에 속합니다.
    Function ID는 Kubernetes namespace 이름에 사용되므로 UUID 형식입니다.

    Namespace 형식: {workspace_name}-{function_uuid}
    예시: alice-dev-550e8400-e29b-41d4-a716-446655440000
    """
    __tablename__ = "functions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
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
