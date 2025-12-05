import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel

from app.models.function import DeploymentStatus, ExecutionType, Runtime


class FunctionBase(BaseModel):
    name: str
    runtime: Runtime
    code: str
    execution_type: ExecutionType


class FunctionCreate(FunctionBase):
    workspace_id: uuid.UUID
    endpoint: Optional[str] = None  # 선택적, 없으면 name 기반으로 자동 생성


class FunctionUpdate(BaseModel):
    name: Optional[str] = None
    runtime: Optional[Runtime] = None
    code: Optional[str] = None
    execution_type: Optional[ExecutionType] = None
    endpoint: Optional[str] = None  # endpoint 수정 가능


class FunctionResponse(FunctionBase):
    id: uuid.UUID
    endpoint: str  # Function 호출 경로
    workspace_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    
    # Deployment tracking
    deployment_status: DeploymentStatus
    knative_url: Optional[str] = None
    last_deployed_at: Optional[datetime] = None
    deployment_error: Optional[str] = None

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


class FunctionDeployRequest(BaseModel):
    """Function 배포 요청"""
    env_vars: Optional[dict] = None  # 추가 환경변수 (선택사항)

    class Config:
        json_schema_extra = {
            "example": {
                "env_vars": {
                    "API_KEY": "secret-key",
                    "ENVIRONMENT": "production"
                }
            }
        }


class FunctionDeployResponse(BaseModel):
    """Function 배포 결과"""
    function_id: uuid.UUID
    function_name: str
    runtime: Runtime
    namespace: str
    service_name: str
    ingress_url: str

    class Config:
        json_schema_extra = {
            "example": {
                "function_id": "550e8400-e29b-41d4-a716-446655440000",
                "function_name": "hello-world",
                "runtime": "PYTHON",
                "namespace": "my-api-550e8400-e29b-41d4-a716-446655440000",
                "service_name": "hello-world",
                "ingress_url": "https://my-api.runna.dev/hello-world"
            }
        }


class FunctionDeploymentStatusResponse(BaseModel):
    """Function 배포 상태 조회 결과"""
    function_id: uuid.UUID
    function_name: str
    deployment_status: DeploymentStatus
    knative_url: Optional[str] = None
    last_deployed_at: Optional[datetime] = None
    deployment_error: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "function_id": "550e8400-e29b-41d4-a716-446655440000",
                "function_name": "hello-world",
                "deployment_status": "DEPLOYED",
                "knative_url": "https://my-api.runna.dev/hello-world",
                "last_deployed_at": "2025-12-05T13:30:00Z",
                "deployment_error": None
            }
        }
