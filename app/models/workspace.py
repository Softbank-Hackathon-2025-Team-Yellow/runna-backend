import re
import uuid
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, validates
from sqlalchemy.sql import func

from app.database import Base


class Workspace(Base):
    """
    Workspace 모델

    하나의 사용자가 소유하는 Function들의 그룹을 나타냄
    각 Workspace는 고유한 UUID를 가지며, 독립적인 인증키를 가질 수 있음

    Workspace name은 Kubernetes namespace 규칙을 따라야 함:
    - 최대 20자 (function ID와 결합 시 63자 제한 준수)
    - 소문자, 숫자, 하이픈(-)만 사용 가능
    - 하이픈으로 시작하거나 끝날 수 없음

    Workspace alias:
    - 불변(immutable) 식별자로 subdomain/namespace 연결에 사용
    - 사용자가 name을 변경해도 alias는 고정되어 URL 안정성 보장
    - 최대 20자, 소문자, 숫자, 하이픈만 허용
    """
    __tablename__ = "workspaces"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String(255), unique=True, nullable=False, index=True)
    alias = Column(String(20), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user = relationship("User", back_populates="workspaces")
    functions = relationship("Function", back_populates="workspace")

    @validates('name')
    def validate_name(self, key, name):
        """
        Workspace name을 Kubernetes namespace 규칙에 맞게 검증

        규칙:
        - 비어있지 않음
        - 최대 20자 (namespace 전체 길이 63자 제한 고려)
        - 소문자, 숫자, 하이픈(-)만 허용
        - 하이픈으로 시작/끝나면 안됨

        Raises:
            ValueError: 규칙에 맞지 않는 경우
        """
        if not name:
            raise ValueError("Workspace name cannot be empty")

        if len(name) > 20:
            raise ValueError(
                "Workspace name must be 20 characters or less "
                "(to ensure namespace length stays under 63 characters)"
            )

        if not re.match(r'^[a-z0-9-]+$', name):
            raise ValueError(
                "Workspace name must contain only lowercase letters, numbers, and hyphens"
            )

        if name.startswith('-') or name.endswith('-'):
            raise ValueError("Workspace name cannot start or end with a hyphen")

        return name

    @validates('alias')
    def validate_alias(self, key, alias):
        """
        Workspace alias를 검증

        규칙:
        - 비어있지 않음
        - 최대 20자
        - 소문자, 숫자, 하이픈(-)만 허용
        - 하이픈으로 시작/끝나면 안됨
        - 불변(immutable) - 한 번 설정되면 변경 불가

        Raises:
            ValueError: 규칙에 맞지 않는 경우
        """
        if not alias:
            raise ValueError("Workspace alias cannot be empty")

        if len(alias) > 20:
            raise ValueError("Workspace alias must be 20 characters or less")

        if not re.match(r'^[a-z0-9-]+$', alias):
            raise ValueError(
                "Workspace alias must contain only lowercase letters, numbers, and hyphens"
            )

        if alias.startswith('-') or alias.endswith('-'):
            raise ValueError("Workspace alias cannot start or end with a hyphen")

        return alias