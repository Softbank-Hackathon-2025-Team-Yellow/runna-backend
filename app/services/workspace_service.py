import uuid
from datetime import timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.security import create_workspace_token
from app.models.function import Function
from app.models.workspace import Workspace
from app.schemas.workspace import WorkspaceCreate, WorkspaceUpdate


class WorkspaceService:
    """
    Workspace 관련 비즈니스 로직 처리
    
    CRUD 작업, 소유권 검증, 인증키 관리 등을 담당
    """
    
    def __init__(self, db: Session):
        self.db = db

    def get_workspace_by_id(self, workspace_id: uuid.UUID) -> Optional[Workspace]:
        """
        ID로 워크스페이스 조회
        
        Args:
            workspace_id: 워크스페이스 UUID
            
        Returns:
            워크스페이스 객체 또는 None
        """
        return self.db.query(Workspace).filter(Workspace.id == workspace_id).first()

    def get_workspace_by_name(self, name: str) -> Optional[Workspace]:
        """
        이름으로 워크스페이스 조회
        
        Args:
            name: 워크스페이스 이름
            
        Returns:
            워크스페이스 객체 또는 None
        """
        return self.db.query(Workspace).filter(Workspace.name == name).first()

    def list_user_workspaces(self, user_id: int) -> List[Workspace]:
        """
        사용자가 소유한 워크스페이스 목록 조회
        
        Args:
            user_id: 사용자 ID
            
        Returns:
            워크스페이스 목록
        """
        return self.db.query(Workspace).filter(Workspace.user_id == user_id).all()

    def create_workspace(self, workspace_data: WorkspaceCreate, user_id: int) -> Workspace:
        """
        새 워크스페이스 생성
        
        Args:
            workspace_data: 워크스페이스 생성 데이터
            user_id: 소유자 사용자 ID
            
        Returns:
            생성된 워크스페이스 객체
            
        Raises:
            ValueError: 워크스페이스 이름이 이미 존재하는 경우
        """
        # 이름 중복 검사
        existing_workspace = self.get_workspace_by_name(workspace_data.name)
        if existing_workspace:
            raise ValueError(f"Workspace with name '{workspace_data.name}' already exists")

        db_workspace = Workspace(
            name=workspace_data.name,
            user_id=user_id
        )
        self.db.add(db_workspace)
        self.db.commit()
        self.db.refresh(db_workspace)
        return db_workspace

    def update_workspace(
        self, 
        workspace_id: uuid.UUID, 
        workspace_data: WorkspaceUpdate, 
        user_id: int
    ) -> Optional[Workspace]:
        """
        워크스페이스 업데이트
        
        Args:
            workspace_id: 워크스페이스 UUID
            workspace_data: 업데이트 데이터
            user_id: 요청한 사용자 ID
            
        Returns:
            업데이트된 워크스페이스 객체 또는 None
            
        Raises:
            ValueError: 이름 중복 또는 권한 없음
        """
        workspace = self.get_workspace_by_id(workspace_id)
        if not workspace:
            return None

        # 소유권 검증
        if workspace.user_id != user_id:
            raise ValueError("You don't have permission to update this workspace")

        # 이름 중복 검사 (변경되는 경우만)
        if workspace_data.name and workspace_data.name != workspace.name:
            existing_workspace = self.get_workspace_by_name(workspace_data.name)
            if existing_workspace:
                raise ValueError(f"Workspace with name '{workspace_data.name}' already exists")
            workspace.name = workspace_data.name

        self.db.commit()
        self.db.refresh(workspace)
        return workspace

    def delete_workspace(self, workspace_id: uuid.UUID, user_id: int) -> bool:
        """
        워크스페이스 삭제
        
        Args:
            workspace_id: 워크스페이스 UUID
            user_id: 요청한 사용자 ID
            
        Returns:
            삭제 성공 여부
            
        Raises:
            ValueError: 권한 없음 또는 Function이 존재하는 경우
        """
        workspace = self.get_workspace_by_id(workspace_id)
        if not workspace:
            return False

        # 소유권 검증
        if workspace.user_id != user_id:
            raise ValueError("You don't have permission to delete this workspace")

        # 연결된 Function이 있는지 확인
        function_count = self.db.query(Function).filter(Function.workspace_id == workspace_id).count()
        if function_count > 0:
            raise ValueError(f"Cannot delete workspace with {function_count} functions. Delete functions first.")

        self.db.delete(workspace)
        self.db.commit()
        return True

    def generate_workspace_auth_key(
        self, 
        workspace_id: uuid.UUID, 
        user_id: int,
        expires_hours: Optional[int] = None
    ) -> str:
        """
        워크스페이스 인증키 생성
        
        Args:
            workspace_id: 워크스페이스 UUID
            user_id: 요청한 사용자 ID
            expires_hours: 만료 시간(시간 단위)
            
        Returns:
            JWT 인증키
            
        Raises:
            ValueError: 워크스페이스를 찾을 수 없거나 권한이 없는 경우
        """
        workspace = self.get_workspace_by_id(workspace_id)
        if not workspace:
            raise ValueError("Workspace not found")

        # 소유권 검증
        if workspace.user_id != user_id:
            raise ValueError("You don't have permission to generate auth key for this workspace")

        # 토큰 생성
        expires_delta = timedelta(hours=expires_hours) if expires_hours else None
        return create_workspace_token(workspace_id, expires_delta)

    def get_workspace_metrics(self, workspace_id: uuid.UUID, user_id: int) -> Optional[dict]:
        """
        워크스페이스 메트릭스 조회
        
        Args:
            workspace_id: 워크스페이스 UUID
            user_id: 요청한 사용자 ID
            
        Returns:
            워크스페이스 메트릭스 또는 None
        """
        workspace = self.get_workspace_by_id(workspace_id)
        if not workspace:
            return None

        # 소유권 검증
        if workspace.user_id != user_id:
            return None

        # Function 개수 조회
        function_count = self.db.query(Function).filter(Function.workspace_id == workspace_id).count()
        
        # Job 관련 메트릭스는 추후 확장 가능
        return {
            "workspace_id": str(workspace_id),
            "name": workspace.name,
            "function_count": function_count,
            "created_at": workspace.created_at,
            "updated_at": workspace.updated_at
        }