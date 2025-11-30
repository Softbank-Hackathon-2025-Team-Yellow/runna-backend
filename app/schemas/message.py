from datetime import datetime
from typing import Any, Optional, Dict
import enum

from pydantic import BaseModel

from app.models.job import JobStatus
from app.models.function import Runtime


class Execution(BaseModel):
    job_id: int
    function_id: int
    payload: Optional[Dict[str, Any]]


class ExecutionStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class Callback(BaseModel):
    job_id: int
    status: ExecutionStatus
    result: Optional[str]
    error: Optional[str]
