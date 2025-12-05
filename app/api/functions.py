from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Body
from sqlalchemy.orm import Session

from app.core.response import create_error_response, create_success_response
from app.database import get_db
from app.dependencies import get_current_user, get_execution_client, get_workspace_auth
from app.models.user import User
from app.models.workspace import Workspace
from app.models.function import Function
from app.infra.execution_client import ExecutionClient
from app.schemas.function import (
    FunctionCreate,
    FunctionResponse,
    FunctionUpdate,
)
from app.schemas.job import JobResponse
from app.services.execution_service import ExecutionService
from app.services.function_service import FunctionService
from app.services.job_service import JobService
from app.services.workspace_service import WorkspaceService

router = APIRouter()


def _validate_function_access(db: Session, function_id: UUID, user_id: int) -> tuple[bool, Optional[Function], Optional[str]]:
    """
    Function에 대한 사용자 접근 권한 검증
    
    Args:
        db: 데이터베이스 세션
        function_id: Function ID
        user_id: 사용자 ID
        
    Returns:
        (접근 가능 여부, Function 객체, 에러 메시지)
    """
    function_service = FunctionService(db)
    function = function_service.get_function(function_id)
    
    if not function:
        return False, None, "Function not found"
    
    workspace_service = WorkspaceService(db)
    workspace = workspace_service.get_workspace_by_id(function.workspace_id)
    
    if not workspace:
        return False, function, "Workspace not found"
        
    if workspace.user_id != user_id:
        return False, function, "You don't have permission to access this function"
        
    return True, function, None


@router.get("/")
def get_functions(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    service = FunctionService(db)
    functions = service.list_functions()
    function_responses = [FunctionResponse.model_validate(f) for f in functions]
    return create_success_response({"functions": function_responses})


@router.post("/")
def create_function(
    function: FunctionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 워크스페이스 소유권 검증
        workspace_service = WorkspaceService(db)
        workspace = workspace_service.get_workspace_by_id(function.workspace_id)
        
        if not workspace:
            return create_error_response(
                "WORKSPACE_NOT_FOUND", f"Workspace with id {function.workspace_id} not found"
            )
            
        if workspace.user_id != current_user.id:
            return create_error_response(
                "ACCESS_DENIED", "You don't have permission to create functions in this workspace"
            )
        
        service = FunctionService(db)
        db_function = service.create_function(function)
        return create_success_response({"function_id": db_function.id})
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.put("/{function_id}")
def update_function(
    function_id: UUID,
    function_update: FunctionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 접근 권한 검증
        has_access, function, error_msg = _validate_function_access(db, function_id, current_user.id)
        if not has_access:
            return create_error_response("ACCESS_DENIED", error_msg)
        
        service = FunctionService(db)
        function = service.update_function(function_id, function_update)
        if not function:
            return create_error_response(
                "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
            )
        return create_success_response({"function_id": function.id})
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{function_id}")
def get_function(
    function_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 접근 권한 검증
    has_access, function, error_msg = _validate_function_access(db, function_id, current_user.id)
    if not has_access:
        return create_error_response("ACCESS_DENIED", error_msg)

    response_data = FunctionResponse.model_validate(function)
    return create_success_response(response_data.model_dump())


@router.delete("/{function_id}")
def delete_function(
    function_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # 접근 권한 검증
    has_access, function, error_msg = _validate_function_access(db, function_id, current_user.id)
    if not has_access:
        return create_error_response("ACCESS_DENIED", error_msg)
    
    service = FunctionService(db)
    success = service.delete_function(function_id)
    if not success:
        return create_error_response(
            "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
        )
    return create_success_response(None)


@router.post("/{function_id}/invoke")
async def invoke_function_with_user_auth(
    function_id: UUID,
    request: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    exec_client: ExecutionClient = Depends(get_execution_client),
    current_user: User = Depends(get_current_user),
):
    """사용자 인증을 통한 Function 실행"""
    try:
        # 접근 권한 검증
        has_access, function, error_msg = _validate_function_access(db, function_id, current_user.id)
        if not has_access:
            return create_error_response("ACCESS_DENIED", error_msg)
        
        service = ExecutionService(db, exec_client)
        job = await service.execute_function(function_id, request)
        job_response = JobResponse.model_validate(job)
        return create_success_response(job_response.model_dump())
    except ValueError as e:
        return create_error_response("FUNCTION_NOT_FOUND", str(e))
    except Exception:
        return create_error_response("EXECUTION_ERROR", "Function execution failed")


@router.post("/{function_id}/invoke/workspace")
async def invoke_function_with_workspace_auth(
    function_id: UUID,
    request: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    exec_client: ExecutionClient = Depends(get_execution_client),
    workspace: Workspace = Depends(get_workspace_auth),
):
    """워크스페이스 인증을 통한 Function 실행"""
    try:
        # Function이 해당 워크스페이스에 속하는지 확인
        function_service = FunctionService(db)
        function = function_service.get_function(function_id)
        
        if not function:
            return create_error_response(
                "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
            )
            
        if function.workspace_id != workspace.id:
            return create_error_response(
                "ACCESS_DENIED", "Function does not belong to the authenticated workspace"
            )
        
        service = ExecutionService(db, exec_client)
        job = await service.execute_function(function_id, request)
        job_response = JobResponse.model_validate(job)
        return create_success_response(job_response.model_dump())
    except ValueError as e:
        return create_error_response("FUNCTION_NOT_FOUND", str(e))
    except Exception:
        return create_error_response("EXECUTION_ERROR", "Function execution failed")


@router.get("/{function_id}/jobs")
def get_function_jobs(
    function_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 접근 권한 검증
        has_access, function, error_msg = _validate_function_access(db, function_id, current_user.id)
        if not has_access:
            return create_error_response("ACCESS_DENIED", error_msg)
        
        service = JobService(db)
        jobs = service.get_job_by_function_id(function_id)
        job_responses = [JobResponse.model_validate(job) for job in jobs]
        return create_success_response(
            {"jobs": [job.model_dump() for job in job_responses]}
        )
    except Exception as e:
        print(e)
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{function_id}/metrics")
def get_function_metrics(
    function_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        # 접근 권한 검증
        has_access, function, error_msg = _validate_function_access(db, function_id, current_user.id)
        if not has_access:
            return create_error_response("ACCESS_DENIED", error_msg)
        
        service = FunctionService(db)
        metrics = service.get_function_metrics(function_id)
        if metrics is None:
            return create_error_response(
                "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
            )
        return create_success_response(metrics)
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")
