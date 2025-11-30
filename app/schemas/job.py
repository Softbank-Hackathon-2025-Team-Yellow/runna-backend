from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

from app.models.job import JobStatus


class JobResponse(BaseModel):
    id: int
    function_id: int
    status: JobStatus
    result: Optional[Any] = None
    timestamp: datetime

    class Config:
        from_attributes = True