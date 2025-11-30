from typing import Any, Dict

from sqlalchemy.orm import Session

from app.infra.execution_client import ExecutionClient
from app.models.function import ExecutionType, Function
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db
        self.exec_service = ExecutionClient()

    def execute_function(
        self, function_id: int, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        function = self.db.query(Function).filter(Function.id == function_id).first()
        if not function:
            raise ValueError("Function not found")

        _job = JobCreate(function_id=function.id, status=JobStatus.PENDING)

        job = Job(**_job.model_dump())

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        if function.execution_type == ExecutionType.SYNC:
            return self._execute_sync(job, input_data)
        else:
            return self._execute_async(job, input_data)

    def _execute_sync(self, job: Job, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.exec_service.insert_exec_queue(job, input_data)
        return job

    def _execute_async(self, job: Job, input_data: Dict[str, Any]) -> Dict[str, Any]:
        self.exec_service.insert_exec_queue(job, input_data)
        return job
