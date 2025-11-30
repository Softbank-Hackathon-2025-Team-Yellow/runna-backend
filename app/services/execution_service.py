from sqlalchemy.orm import Session
from typing import List, Optional, Union, Dict, Any
import json
from datetime import datetime
import uuid

from app.models.function import Function, ExecutionType
from app.models.job import Job, JobStatus
from app.schemas.job import JobResponse
from app.core.knative_client import knative_client
from app.infra.execution_client import ExecutionClient


class ExecutionService:
    def __init__(self, db: Session):
        self.db = db

    def execute_function(
        self, function_id: int, input_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        function = self.db.query(Function).filter(Function.id == function_id).first()
        if not function:
            raise ValueError("Function not found")

        if function.execution_type == ExecutionType.SYNC:
            return self._execute_sync(function, input_data)
        else:
            return self._execute_async(function, input_data)

    def _execute_sync(self, job: Job, input_data: Dict[str, Any]) -> Dict[str, Any]:
        ExecutionClient.insert_exec_queue(job, input_data)
        pass

    def _execute_async(self, job: Job, input_data: Dict[str, Any]) -> Dict[str, Any]:
        ExecutionClient.insert_exec_queue(job, input_data)
        pass
