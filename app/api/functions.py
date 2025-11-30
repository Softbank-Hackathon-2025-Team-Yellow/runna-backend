from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas.function import FunctionCreate, FunctionUpdate, FunctionResponse, FunctionCreateResponse, CommonApiResponse, InvokeFunctionRequest
from app.schemas.job import JobResponse
from app.services.function_service import FunctionService
from app.services.execution_service import ExecutionService
from app.core.response import create_success_response, create_error_response

router = APIRouter()


@router.get("/")
def get_functions(db: Session = Depends(get_db)):
    service = FunctionService(db)
    functions = service.list_functions()
    function_responses = [FunctionResponse.model_validate(f) for f in functions]
    return create_success_response({"functions": function_responses})


@router.post("/")
def create_function(
    function: FunctionCreate,
    db: Session = Depends(get_db)
):
    try:
        service = FunctionService(db)
        db_function = service.create_function(function)
        return create_success_response({"function_id": db_function.id})
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception as e:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.put("/{function_id}")
def update_function(
    function_id: int,
    function_update: FunctionUpdate,
    db: Session = Depends(get_db)
):
    try:
        service = FunctionService(db)
        function = service.update_function(function_id, function_update)
        if not function:
            return create_error_response("FUNCTION_NOT_FOUND", f"Function with id {function_id} not found")
        return create_success_response({"function_id": function.id})
    except ValueError as e:
        return create_error_response("VALIDATION_ERROR", str(e))
    except Exception as e:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{function_id}")
def get_function(
    function_id: int,
    db: Session = Depends(get_db)
):
    service = FunctionService(db)
    function = service.get_function(function_id)
    if not function:
        return create_error_response("FUNCTION_NOT_FOUND", f"Function with id {function_id} not found")
    
    response_data = FunctionResponse.model_validate(function)
    return create_success_response(response_data.model_dump())


@router.delete("/{function_id}")
def delete_function(
    function_id: int,
    db: Session = Depends(get_db)
):
    service = FunctionService(db)
    success = service.delete_function(function_id)
    if not success:
        return create_error_response("FUNCTION_NOT_FOUND", f"Function with id {function_id} not found")
    return create_success_response(None)


@router.post("/{function_id}/invoke")
def invoke_function(
    function_id: int,
    request: InvokeFunctionRequest,
    db: Session = Depends(get_db)
):
    try:
        service = ExecutionService(db)
        result = service.execute_function(function_id, request.to_dict())
        return create_success_response(result)
    except ValueError as e:
        return create_error_response("FUNCTION_NOT_FOUND", str(e))
    except Exception as e:
        return create_error_response("EXECUTION_ERROR", "Function execution failed")


@router.get("/{function_id}/jobs")
def get_function_jobs(
    function_id: int,
    db: Session = Depends(get_db)
):
    try:
        service = ExecutionService(db)
        jobs = service.get_function_jobs(function_id)
        return create_success_response({"jobs": jobs})
    except Exception as e:
        return create_error_response("INTERNAL_ERROR", "Internal server error")


@router.get("/{function_id}/metrics")
def get_function_metrics(
    function_id: int,
    db: Session = Depends(get_db)
):
    try:
        service = FunctionService(db)
        metrics = service.get_function_metrics(function_id)
        if metrics is None:
            return create_error_response("FUNCTION_NOT_FOUND", f"Function with id {function_id} not found")
        return create_success_response(metrics)
    except Exception as e:
        return create_error_response("INTERNAL_ERROR", "Internal server error")