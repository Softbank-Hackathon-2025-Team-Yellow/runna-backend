import uuid
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.models.job import JobStatus, JobType


class JobBase(BaseModel):
    function_id: uuid.UUID
    status: JobStatus


class JobCreate(JobBase):
    pass


class JobUpdate(BaseModel):
    function_id: Optional[uuid.UUID] = None
    status: Optional[JobStatus] = None
    result: Optional[str] = None


class JobResponse(BaseModel):
    job_id: int = Field(validation_alias="id")
    function_id: uuid.UUID
    job_type: JobType
    status: JobStatus
    result: Optional[Any] = None
    timestamp: datetime

    class Config:
        from_attributes = True
