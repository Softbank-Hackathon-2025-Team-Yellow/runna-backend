from sqlalchemy.orm import Session
from typing import List, Optional

from app.models.job import Job, JobStatus
from app.models.execution import Execution


class JobService:
    def __init__(self, db: Session):
        self.db = db

    def get_job_by_job_id(self, job_id: int) -> Optional[Job]:
        return self.db.query(Job).filter(Job.job_id == job_id).first()

    def update_job_status(
        self,
        job_id: int,
        status: JobStatus,
        result: Optional[str] = None
    ) -> Optional[Job]:
        job = self.get_job_by_job_id(job_id)
        if not job:
            return None

        job.status = status
        if result:
            job.result = result

        self.db.commit()
        self.db.refresh(job)
        return job