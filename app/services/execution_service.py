from sqlalchemy.orm import Session
from typing import List, Optional, Union, Dict, Any
import json
from datetime import datetime
import uuid

from app.models.function import Function, ExecutionType
from app.models.job import Job, JobStatus
from app.schemas.job import JobResponse
from app.core.knative_client import knative_client


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def execute_function(self, function_id: int, input_data: Dict[str, Any]) -> Dict[str, Any]:
        function = self.db.query(Function).filter(Function.id == function_id).first()
        if not function:
            raise ValueError("Function not found")

        if function.execution_type == ExecutionType.SYNC:
            return self._execute_sync(function, input_data)
        else:
            return self._execute_async(function, input_data)

    def _execute_sync(self, function: Function, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Create job with RUNNING status for sync execution
        db_job = Job(
            function_id=function.id,
            status=JobStatus.RUNNING,
            result=None
        )
        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)

        try:
            result = knative_client.execute_function_sync(
                function.name,
                function.code,
                function.runtime.value,
                input_data
            )
            
            if result.get("success", False):
                db_job.status = JobStatus.SUCCEEDED
                result_data = result.get("output")
                db_job.result = json.dumps(result_data) if result_data else None
            else:
                db_job.status = JobStatus.FAILED
                result_data = None
                db_job.result = None

            self.db.commit()
            self.db.refresh(db_job)

            return {
                "id": db_job.id,
                "function_id": function.id,
                "status": db_job.status.value,
                "result": result_data,
                "timestamp": db_job.timestamp.isoformat()
            }

        except Exception as e:
            db_job.status = JobStatus.FAILED
            db_job.result = None
            self.db.commit()
            self.db.refresh(db_job)

            return {
                "id": db_job.id,
                "function_id": function.id,
                "status": JobStatus.FAILED.value,
                "result": None,
                "timestamp": db_job.timestamp.isoformat()
            }

    def _execute_async(self, function: Function, input_data: Dict[str, Any]) -> Dict[str, Any]:
        # Create job with PENDING status for async execution
        db_job = Job(
            function_id=function.id,
            status=JobStatus.PENDING,
            result=None
        )
        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)

        # TODO: Implement async execution with background task queue
        # For now, return pending status immediately

        return {
            "id": db_job.id,
            "function_id": function.id,
            "status": JobStatus.PENDING.value,
            "result": None,
            "timestamp": db_job.timestamp.isoformat()
        }

    def get_function_jobs(self, function_id: int) -> List[Dict[str, Any]]:
        jobs = self.db.query(Job).filter(
            Job.function_id == function_id
        ).order_by(Job.timestamp.desc()).all()

        return [
            {
                "id": job.id,
                "function_id": job.function_id,
                "status": job.status.value,
                "timestamp": job.timestamp.isoformat(),
                "result": json.loads(job.result) if job.result else None
            }
            for job in jobs
        ]