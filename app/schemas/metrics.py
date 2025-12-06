"""
메트릭 관련 스키마 정의

Prometheus 응답을 기반으로 하는 Pydantic 모델들
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PodMetrics(BaseModel):
    """Pod 관련 메트릭"""

    current_count: int = Field(description="현재 실행 중인 Pod 수")
    desired_count: int = Field(description="원하는 Pod 수")
    pending_count: int = Field(default=0, description="대기 중인 Pod 수")


class ConcurrencyMetrics(BaseModel):
    """동시성 관련 메트릭"""

    target: float = Field(description="목표 동시성")
    stable: float = Field(description="안정적 동시성")
    panic_mode: bool = Field(default=False, description="패닉 모드 여부")


class RequestMetrics(BaseModel):
    """요청 처리 메트릭"""

    total_count: int = Field(description="총 요청 수")
    avg_duration_seconds: Optional[float] = Field(
        default=None, description="평균 처리 시간(초)"
    )


class FunctionMetrics(BaseModel):
    """함수 통합 메트릭"""

    service_name: str = Field(description="Knative 서비스 이름")
    namespace: str = Field(description="Kubernetes 네임스페이스")
    revision_name: Optional[str] = Field(default=None, description="Revision 이름")

    pods: PodMetrics = Field(description="Pod 메트릭")
    concurrency: ConcurrencyMetrics = Field(description="동시성 메트릭")
    requests: Optional[RequestMetrics] = Field(
        default=None, description="요청 메트릭 (있는 경우)"
    )

    capacity_excess: float = Field(default=0.0, description="초과 용량")
    timestamp: datetime = Field(description="메트릭 수집 시간")

    class Config:
        json_schema_extra = {
            "example": {
                "service_name": "inline-test-runner",
                "namespace": "default",
                "revision_name": "inline-test-runner-00001",
                "pods": {"current_count": 1, "desired_count": 1, "pending_count": 0},
                "concurrency": {"target": 100.0, "stable": 50.0, "panic_mode": False},
                "requests": {"total_count": 16, "avg_duration_seconds": 0.05},
                "capacity_excess": 0.0,
                "timestamp": "2025-12-06T15:30:00Z",
            }
        }
