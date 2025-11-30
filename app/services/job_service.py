from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.job import Job, JobStatus


class JobService:
    def __init__(self, db: Session):
        self.db = db

    def get_job_by_id(self, id: int) -> Optional[Job]:
        return self.db.query(Job).filter(Job.id == id).first()

    def get_job_by_function_id(self, function_id: int) -> List[Job]:
        return self.db.query(Job).filter(Job.function_id == function_id).all()

    def update_job_status(
        self, id: int, status: JobStatus, result: Optional[str] = None
    ) -> Optional[Job]:
        job = self.get_job_by_id(id)
        if not job:
            return None

        job.status = status
        if result:
            job.result = result

        self.db.commit()
        self.db.refresh(job)
        return job
