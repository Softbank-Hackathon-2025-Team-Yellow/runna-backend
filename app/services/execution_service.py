from sqlalchemy.orm import Session
from typing import List, Optional, Union, Dict, Any
import json
from datetime import datetime
import uuid

from app.models.execution import Execution, ExecutionStatus
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

        if not function.is_active:
            raise ValueError("Function is not active")

        db_execution = Execution(
            function_id=function_id,
            input_data=json.dumps(input_data) if input_data else None,
            status=ExecutionStatus.PENDING
        )
        self.db.add(db_execution)
        self.db.commit()
        self.db.refresh(db_execution)

        if function.execution_type == ExecutionType.SYNC:
            return self._execute_sync(db_execution, function)
        else:
            return self._execute_async(db_execution, function)

    def _execute_sync(self, execution: Execution, function: Function) -> Dict[str, Any]:
        execution.status = ExecutionStatus.RUNNING
        self.db.commit()

        try:
            input_data = json.loads(execution.input_data) if execution.input_data else {}
            result = knative_client.execute_function_sync(
                function.name,
                function.code,
                function.runtime.value,
                input_data
            )

            job_id = self._generate_job_id()
            
            if result.get("success", False):
                status = JobStatus.SUCCEEDED
                result_data = result.get("output")
            else:
                status = JobStatus.FAILED
                result_data = None

            db_job = Job(
                job_id=job_id,
                execution_id=execution.id,
                status=status,
                result=json.dumps(result_data) if result_data else None
            )
            self.db.add(db_job)
            self.db.commit()
            self.db.refresh(db_job)

            return {
                "job_id": job_id,
                "status": status.value,
                "result": result_data,
                "timestamp": db_job.timestamp.isoformat()
            }

        except Exception as e:
            job_id = self._generate_job_id()
            db_job = Job(
                job_id=job_id,
                execution_id=execution.id,
                status=JobStatus.FAILED,
                result=None
            )
            self.db.add(db_job)
            self.db.commit()

            return {
                "job_id": job_id,
                "status": JobStatus.FAILED.value,
                "result": None,
                "timestamp": db_job.timestamp.isoformat()
            }

    def _execute_async(self, execution: Execution, function: Function) -> Dict[str, Any]:
        job_id = self._generate_job_id()
        
        db_job = Job(
            job_id=job_id,
            execution_id=execution.id,
            status=JobStatus.PENDING
        )
        self.db.add(db_job)
        self.db.commit()
        self.db.refresh(db_job)

        return {
            "job_id": job_id,
            "status": JobStatus.PENDING.value,
            "result": None,
            "timestamp": db_job.timestamp.isoformat()
        }

    def get_function_jobs(self, function_id: int) -> List[Dict[str, Any]]:
        jobs = self.db.query(Job).join(Execution).filter(
            Execution.function_id == function_id
        ).order_by(Job.timestamp.desc()).all()

        return [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "timestamp": job.timestamp.isoformat(),
                "result": json.loads(job.result) if job.result else None
            }
            for job in jobs
        ]

    def _generate_job_id(self) -> int:
        return int(str(uuid.uuid4().int)[:10])