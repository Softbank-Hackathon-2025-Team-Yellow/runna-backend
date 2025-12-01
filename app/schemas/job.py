from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

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


class JobResponse(BaseModel):
    job_id: int = Field(validation_alias="id")
    function_id: int
    status: JobStatus
    result: Optional[Any] = None
    timestamp: datetime

    class Config:
        from_attributes = True
        populate_by_name = True
