from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.schemas.job import JobResponse
from app.services.job_service import JobService
from app.core.response import create_success_response, create_error_response

router = APIRouter()


@router.get("/{job_id}")
def get_job(
    job_id: int,
    db: Session = Depends(get_db)
):
    service = JobService(db)
    job = service.get_job_by_job_id(job_id)
    if not job:
        return create_error_response("JOB_NOT_FOUND", f"Job with id {job_id} not found")
    
    job_response = JobResponse.from_orm(job)
    return create_success_response(job_response.dict())