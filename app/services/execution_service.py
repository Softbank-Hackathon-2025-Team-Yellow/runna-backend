import json
from typing import Any, Dict

from sqlalchemy.orm import Session

from app.infra.execution_client import ExecutionClient
from app.models.function import ExecutionType, Function
from app.models.job import Job, JobStatus
from app.schemas.job import JobCreate


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    async def execute_function(
        self, function_id: int, input_data: Dict[str, Any]
    ) -> Job:
        """
        함수를 실행합니다.
        
        변경사항:
          - 반환 타입을 Dict[str, Any]에서 Job으로 변경하여 타입이 지정된 SQLAlchemy 객체를 제공합니다.
          - Non-blocking I/O (Redis) 지원을 위해 async로 변경했습니다.
        """
        function = self.db.query(Function).filter(Function.id == function_id).first()
        if not function:
            raise ValueError("Function not found")

        _job = JobCreate(function_id=function.id, status=JobStatus.PENDING)

        job = Job(**_job.model_dump())

        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        if function.execution_type == ExecutionType.SYNC:
            return await self._execute_sync(job, input_data)
        else:
            return await self._execute_async(job, input_data)

    async def _execute_sync(self, job: Job, input_data: Dict[str, Any]) -> Job:
        """
        변경사항: 일관성을 위해 반환 타입을 Dict에서 Job으로 변경했습니다.
        """
        try:
            # Sync execution: Invoke via Redis and wait for result
            result = await ExecutionClient.invoke_sync(job, input_data)
            
            # Update Job status to SUCCEEDED and save result
            job.status = JobStatus.SUCCEEDED
            job.result = json.dumps(result) # Result is dict, save as JSON string
        except Exception as e:
            # Update Job status to FAILED
            job.status = JobStatus.FAILED
            job.result = str(e)
        
        self.db.commit()
        self.db.refresh(job)
        return job

    async def _execute_async(self, job: Job, input_data: Dict[str, Any]) -> Job:
        """
        변경사항: 일관성을 위해 반환 타입을 Dict에서 Job으로 변경했습니다.
        """
        try:
            # Async execution: Enqueue to Redis
            await ExecutionClient.insert_exec_queue(job, input_data)
            
            # Update Job status to ACCEPTED (or PENDING) to indicate it's in queue
            # We use ACCEPTED to match the API response expectation for 202
            # job.status = JobStatus.ACCEPTED 
            pass 
        except Exception as e:
            # If enqueue fails, mark as FAILED
            job.status = JobStatus.FAILED
            job.result = f"Failed to enqueue: {str(e)}"
        
        self.db.commit()
        self.db.refresh(job)
        return job
