import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends
from sqlalchemy.orm import Session

from app.core.response import create_error_response, create_success_response
from app.core.sanitize import SanitizationError, sanitize_workspace_name
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.function import FunctionResponse
from app.schemas.workspace import (
    WorkspaceAuthKey,
    WorkspaceCreate,
    WorkspaceResponse,
    WorkspaceUpdate,
)
from app.services.workspace_service import WorkspaceService

router = APIRouter()


@router.get("/", response_model=dict)
def get_workspaces(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """
    현재 사용자의 워크스페이스 목록 조회

    Args:
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        사용자 워크스페이스 목록
    """
    service = WorkspaceService(db)
    workspaces = service.list_user_workspaces(current_user.id)
    workspace_responses = [WorkspaceResponse.model_validate(w) for w in workspaces]
    return create_success_response(
        {"workspaces": [w.model_dump() for w in workspace_responses]}
    )


@router.post("/", response_model=dict)
def create_workspace(
    workspace: WorkspaceCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    새 워크스페이스 생성

    Args:
        workspace: 워크스페이스 생성 데이터
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        생성된 워크스페이스 정보
    """
    try:
        # API Layer: First line of defense - sanitize user input
        sanitized_name = sanitize_workspace_name(workspace.name, strict=True)
        workspace.name = sanitized_name

        service = WorkspaceService(db)
        db_workspace = service.create_workspace(workspace, current_user.id)
        workspace_response = WorkspaceResponse.model_validate(db_workspace)
        return create_success_response(workspace_response.model_dump())
    except SanitizationError as e:
        return create_error_response("SANITIZATION_ERROR", str(e))
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{workspace_id}", response_model=dict)
def get_workspace(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    특정 워크스페이스 조회

    Args:
        workspace_id: 워크스페이스 UUID
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        워크스페이스 정보
    """
    try:
        service = WorkspaceService(db)
        workspace = service.get_workspace_by_id(workspace_id)

        if not workspace:
            return create_error_response(
                "WORKSPACE_NOT_FOUND", f"Workspace with id {workspace_id} not found"
            )

        # 소유권 검증
        if workspace.user_id != current_user.id:
            return create_error_response(
                "ACCESS_DENIED", "You don't have permission to access this workspace"
            )

        workspace_response = WorkspaceResponse.model_validate(workspace)
        return create_success_response(workspace_response.model_dump())
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.put("/{workspace_id}", response_model=dict)
def update_workspace(
    workspace_id: uuid.UUID,
    workspace_update: WorkspaceUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    워크스페이스 업데이트

    Args:
        workspace_id: 워크스페이스 UUID
        workspace_update: 업데이트 데이터
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        업데이트된 워크스페이스 정보
    """
    try:
        # API Layer: Sanitize workspace name if provided
        if workspace_update.name:
            sanitized_name = sanitize_workspace_name(workspace_update.name, strict=True)
            workspace_update.name = sanitized_name

        service = WorkspaceService(db)
        workspace = service.update_workspace(
            workspace_id, workspace_update, current_user.id
        )

        if not workspace:
            return create_error_response(
                "WORKSPACE_NOT_FOUND", f"Workspace with id {workspace_id} not found"
            )

        workspace_response = WorkspaceResponse.model_validate(workspace)
        return create_success_response(workspace_response.model_dump())
    except SanitizationError as e:
        return create_error_response("SANITIZATION_ERROR", str(e))
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.delete("/{workspace_id}", response_model=dict)
def delete_workspace(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    워크스페이스 삭제

    Args:
        workspace_id: 워크스페이스 UUID
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        삭제 성공 응답
    """
    try:
        service = WorkspaceService(db)
        success = service.delete_workspace(workspace_id, current_user.id)

        if not success:
            return create_error_response(
                "WORKSPACE_NOT_FOUND", f"Workspace with id {workspace_id} not found"
            )

        return create_success_response(None)
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.post("/{workspace_id}/auth-keys", response_model=dict)
def generate_workspace_auth_key(
    workspace_id: uuid.UUID,
    expires_hours: Optional[int] = Body(default=None, embed=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    워크스페이스 인증키 발급

    Args:
        workspace_id: 워크스페이스 UUID
        expires_hours: 만료 시간(시간 단위, 기본값 24시간)
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        워크스페이스 인증키
    """
    try:
        service = WorkspaceService(db)
        auth_key = service.generate_workspace_auth_key(
            workspace_id, current_user.id, expires_hours
        )

        auth_key_response = WorkspaceAuthKey(
            workspace_id=workspace_id, auth_key=auth_key
        )
        return create_success_response(auth_key_response.model_dump())
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{workspace_id}/metrics", response_model=dict)
def get_workspace_metrics(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    워크스페이스 메트릭스 조회

    Args:
        workspace_id: 워크스페이스 UUID
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        워크스페이스 메트릭스 정보
    """
    try:
        service = WorkspaceService(db)
        metrics = service.get_workspace_metrics(workspace_id, current_user.id)

        if metrics is None:
            return create_error_response(
                "WORKSPACE_NOT_FOUND", f"Workspace with id {workspace_id} not found"
            )

        return create_success_response(metrics)
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{workspace_id}/functions", response_model=dict)
def get_workspace_functions(
    workspace_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    워크스페이스에 속한 Function 목록 조회

    Args:
        workspace_id: 워크스페이스 UUID
        db: 데이터베이스 세션
        current_user: 인증된 현재 사용자

    Returns:
        워크스페이스 Function 목록
    """
    try:
        workspace_service = WorkspaceService(db)
        workspace = workspace_service.get_workspace_by_id(workspace_id)

        if not workspace:
            return create_error_response(
                "WORKSPACE_NOT_FOUND", f"Workspace with id {workspace_id} not found"
            )

        # 소유권 검증
        if workspace.user_id != current_user.id:
            return create_error_response(
                "ACCESS_DENIED", "You don't have permission to access this workspace"
            )

        # 워크스페이스에 속한 Function 조회
        from app.models.function import Function

        functions = (
            db.query(Function).filter(Function.workspace_id == workspace_id).all()
        )
        function_responses = [FunctionResponse.model_validate(f) for f in functions]

        return create_success_response(
            {
                "workspace_id": str(workspace_id),
                "functions": [f.model_dump() for f in function_responses],
            }
        )
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")
