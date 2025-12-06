from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.response import create_error_response, create_success_response
from app.database import get_db
from app.dependencies import get_current_user
from app.models.user import User
from app.models.job import JobType
from app.schemas.job import JobResponse
from app.services.job_service import JobService


router = APIRouter()


@router.get("/{id}")
def get_job(
    id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Job 상태 조회
    
    - DEPLOYMENT Job의 경우 Future에서 실시간 상태 확인
    - EXECUTION Job의 경우 DB에서 조회
    """
    service = JobService(db)
    job = service.get_job_by_id(id)
    if not job:
        return create_error_response("JOB_NOT_FOUND", f"Job with id {id} not found")

    job_response = JobResponse.model_validate(job)
    response_data = job_response.model_dump()
    
    
    # DEPLOYMENT Job 제거됨, 일반 Job 처럼 DB 조회 결과만 반환
    # (JobType.DEPLOYMENT는 이제 존재하지 않거나 사용되지 않음)

    
    return create_success_response(response_data)
