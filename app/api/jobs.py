from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas.job import JobResponse
from app.services.job_service import JobService
from app.core.response import create_success_response, create_error_response

router = APIRouter()


@router.get("/{id}")
def get_job(
    id: int,
    db: Session = Depends(get_db)
):
    service = JobService(db)
    job = service.get_job_by_id(id)
    if not job:
        return create_error_response("JOB_NOT_FOUND", f"Job with id {id} not found")
    
    job_response = JobResponse.model_validate(job)
    return create_success_response(job_response.model_dump())