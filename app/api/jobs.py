
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import create_error_response, create_success_response
from app.database import get_db
from app.schemas.job import JobResponse
from app.services.job_service import JobService

router = APIRouter()


@router.get("/{id}", response_model=JobResponse)
def get_job(id: int, db: Session = Depends(get_db)):
    service = JobService(db)
    job = service.get_job_by_id(id)
    if not job:
        # return create_error_response("JOB_NOT_FOUND", f"Job with id {id} not found")
        # Using HTTPException for consistency with other updated endpoints
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Job with id {id} not found")

    return job
