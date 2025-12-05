import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class WorkspaceBase(BaseModel):
    """
    Workspace 기본 스키마
    
    Args:
        name: 워크스페이스 이름 (고유해야 함)
    """
    name: str


class WorkspaceCreate(WorkspaceBase):
    """
    Workspace 생성 스키마
    
    Args:
        name: 워크스페이스 이름
    """
    pass


class WorkspaceUpdate(BaseModel):
    """
    Workspace 업데이트 스키마
    
    Args:
        name: 변경할 워크스페이스 이름 (선택사항)
    """
    name: Optional[str] = None


class WorkspaceResponse(WorkspaceBase):
    """
    Workspace 응답 스키마

    Args:
        id: 워크스페이스 UUID
        name: 워크스페이스 이름
        alias: 워크스페이스 불변 식별자 (subdomain/namespace 연결용)
        user_id: 소유자 사용자 ID
        created_at: 생성 일시
        updated_at: 수정 일시
    """
    id: uuid.UUID
    alias: str
    user_id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WorkspaceAuthKey(BaseModel):
    """
    Workspace 인증키 응답 스키마
    
    Args:
        workspace_id: 워크스페이스 UUID
        auth_key: 인증키 (Bearer 토큰)
        expires_at: 만료 일시 (선택사항)
    """
    workspace_id: uuid.UUID
    auth_key: str
    expires_at: Optional[datetime] = None


class WorkspaceWithFunctionCount(WorkspaceResponse):
    """
    Function 개수가 포함된 Workspace 응답 스키마
    
    Args:
        function_count: 워크스페이스에 포함된 Function 개수
    """
    function_count: int