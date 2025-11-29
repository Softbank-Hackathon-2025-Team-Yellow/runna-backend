from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.models.function import Runtime, ExecutionType


class FunctionBase(BaseModel):
    name: str
    runtime: Runtime
    code: str
    execution_type: ExecutionType


class FunctionCreate(FunctionBase):
    pass


class FunctionUpdate(BaseModel):
    name: Optional[str] = None
    runtime: Optional[Runtime] = None
    code: Optional[str] = None
    execution_type: Optional[ExecutionType] = None


class FunctionResponse(FunctionBase):
    function_id: int

    class Config:
        orm_mode = True

    @classmethod
    def from_orm(cls, obj):
        return cls(
            name=obj.name,
            runtime=obj.runtime,
            code=obj.code,
            execution_type=obj.execution_type,
            function_id=obj.id
        )


class CommonApiResponse(BaseModel):
    success: bool
    data: Optional[dict] = None
    error: Optional[dict] = None


class FunctionCreateResponse(BaseModel):
    function_id: int