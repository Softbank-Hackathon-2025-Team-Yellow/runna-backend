import enum
import re
import uuid

from sqlalchemy import Column, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.database import Base


class Runtime(str, enum.Enum):
    PYTHON = "PYTHON"
    NODEJS = "NODEJS"


class ExecutionType(str, enum.Enum):
    SYNC = "SYNC"
    ASYNC = "ASYNC"


class Function(Base):
    """
    Function 모델

    각 Function은 고유한 UUID를 가지며, Workspace에 속합니다.
    Function ID는 Kubernetes namespace 이름에 사용되므로 UUID 형식입니다.

    Namespace 형식: {workspace_name}-{function_uuid}
    예시: alice-dev-550e8400-e29b-41d4-a716-446655440000

    Function endpoint:
    - 사용자 정의 가능한 URL 경로
    - 형식: /{endpoint} (예: /my-function)
    - 전체 URL: https://runna.io/{workspace_alias}/{endpoint}
    - 전역적으로 unique해야 함
    - 최대 100자, URL-safe 문자만 허용
    """
    __tablename__ = "functions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), unique=False, index=True, nullable=False)
    endpoint = Column(String(100), nullable=False, index=True)  # unique=True 제거
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

    # Composite unique constraint: workspace 내에서만 endpoint가 unique
    __table_args__ = (
        UniqueConstraint('workspace_id', 'endpoint', name='uq_workspace_endpoint'),
    )

    @validates('endpoint')
    def validate_endpoint(self, key, endpoint):
        """
        Function endpoint를 검증

        규칙:
        - 비어있지 않음
        - 슬래시(/)로 시작해야 함
        - 최대 100자
        - URL-safe 문자만 허용: [a-z0-9-/]
        - 하이픈으로 시작/끝 불가 (슬래시 제외)
        - 연속된 하이픈 불가
        - 연속된 슬래시 불가

        Raises:
            ValueError: 규칙에 맞지 않는 경우
        """
        if not endpoint:
            raise ValueError("Function endpoint cannot be empty")

        if not endpoint.startswith('/'):
            raise ValueError("Function endpoint must start with '/'")

        if len(endpoint) > 100:
            raise ValueError("Function endpoint must be 100 characters or less")

        # URL-safe 문자만 허용: 소문자, 숫자, 하이픈, 슬래시
        if not re.match(r'^/[a-z0-9/-]+$', endpoint):
            raise ValueError(
                "Function endpoint must contain only lowercase letters, numbers, hyphens, and slashes"
            )

        # 연속된 하이픈 불가
        if '--' in endpoint:
            raise ValueError("Function endpoint cannot contain consecutive hyphens")

        # 연속된 슬래시 불가
        if '//' in endpoint:
            raise ValueError("Function endpoint cannot contain consecutive slashes")

        # 하이픈으로 끝나면 안됨
        if endpoint.endswith('-'):
            raise ValueError("Function endpoint cannot end with a hyphen")

        return endpoint
