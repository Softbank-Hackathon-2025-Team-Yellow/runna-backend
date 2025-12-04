import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.function import ExecutionType, Runtime


class FunctionBase(BaseModel):
    name: str
    runtime: Runtime
    code: str
    execution_type: ExecutionType


class FunctionCreate(FunctionBase):
    workspace_id: uuid.UUID


class FunctionUpdate(BaseModel):
    name: Optional[str] = None
    runtime: Optional[Runtime] = None
    code: Optional[str] = None
    execution_type: Optional[ExecutionType] = None


class FunctionResponse(FunctionBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CommonApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None


class FunctionCreateResponse(BaseModel):
    function_id: uuid.UUID


class InvokeFunctionRequest(BaseModel):
    param1: Optional[str] = None
    param2: Optional[str] = None

    def to_dict(self) -> dict:
        """Convert request to dictionary for function execution"""
        return {k: v for k, v in self.model_dump().items() if v is not None}
