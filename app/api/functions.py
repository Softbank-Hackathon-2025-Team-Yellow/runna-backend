
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.response import create_error_response, create_success_response
from app.database import get_db
from app.schemas.function import (
    FunctionCreate,
    FunctionResponse,
    FunctionUpdate,
    InvokeFunctionRequest,
)
from app.models.job import JobStatus
from app.schemas.job import JobResponse
from app.services.execution_service import ExecutionService
from app.services.function_service import FunctionService
from app.services.job_service import JobService

router = APIRouter()


@router.get("/")
def get_functions(db: Session = Depends(get_db)):
    service = FunctionService(db)
    functions = service.list_functions()
    function_responses = [FunctionResponse.model_validate(f) for f in functions]
    return create_success_response({"functions": function_responses})


@router.post("/")
def create_function(function: FunctionCreate, db: Session = Depends(get_db)):
    try:
        service = FunctionService(db)
        db_function = service.create_function(function)
        return create_success_response({"function_id": db_function.id})
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.put("/{function_id}")
def update_function(
    function_id: int, function_update: FunctionUpdate, db: Session = Depends(get_db)
):
    try:
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
def get_function(function_id: int, db: Session = Depends(get_db)):
    service = FunctionService(db)
    function = service.get_function(function_id)
    if not function:
        return create_error_response(
            "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
        )

    response_data = FunctionResponse.model_validate(function)
    return create_success_response(response_data.model_dump())


@router.delete("/{function_id}")
def delete_function(function_id: int, db: Session = Depends(get_db)):
    service = FunctionService(db)
    success = service.delete_function(function_id)
    if not success:
        return create_error_response(
            "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
        )
    return create_success_response(None)


@router.post("/{function_id}/invoke", response_model=JobResponse)
async def invoke_function(
    function_id: int,
    request: InvokeFunctionRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    변경사항:
      - `ExecutionService`의 Non-blocking I/O 지원을 위해 `async def`로 변경했습니다.
      - 더 나은 타입 안전성을 위해 Dict 대신 `Job` 객체(JobResponse로 매핑됨)를 반환합니다.
    """
    try:
        service = ExecutionService(db)
        job = await service.execute_function(function_id, request.model_dump().get("input", {}))
        
        # Set status code based on job status
        if job.status == JobStatus.PENDING:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
            
        return job
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Log error
        print(f"Execution error: {e}")
        raise HTTPException(status_code=500, detail="Function execution failed")


@router.get("/{function_id}/jobs", response_model=List[JobResponse])
def get_function_jobs(function_id: int, db: Session = Depends(get_db)):
    try:
        service = JobService(db)
        jobs = service.get_job_by_function_id(function_id)
        return jobs
    except Exception as e:
        print(e)
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/{function_id}/metrics")
def get_function_metrics(function_id: int, db: Session = Depends(get_db)):
    try:
        service = FunctionService(db)
        metrics = service.get_function_metrics(function_id)
        if metrics is None:
            return create_error_response(
                "FUNCTION_NOT_FOUND", f"Function with id {function_id} not found"
            )
        return create_success_response(metrics)
    except Exception:
        return create_error_response("INTERNAL_ERROR", "Internal server error")
