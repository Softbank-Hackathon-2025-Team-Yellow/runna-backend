import enum
from typing import Any, Dict, Optional

from pydantic import BaseModel


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
