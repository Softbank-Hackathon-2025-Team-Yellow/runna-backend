from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

from app.models.job import JobStatus


class JobBase(BaseModel):
    function_id: int
    status: JobStatus


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    function_id: Optional[int] = None
    status: Optional[JobStatus] = None
    result: Optional[str] = None


class JobResponse(JobBase):
    id: int
    result: Optional[Any] = None
    timestamp: datetime

    class Config:
        from_attributes = True