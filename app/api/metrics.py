"""
메트릭 API 엔드포인트

Knative 서비스 메트릭을 조회하는 API를 제공합니다.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.infra.metrics_client import MetricsClient
from app.schemas.metrics import ConcurrencyMetrics, FunctionMetrics, PodMetrics
from app.services.metrics_service import MetricsService, MetricsServiceError

logger = logging.getLogger(__name__)

router = APIRouter()

# MetricsService 의존성
_metrics_service: Optional[MetricsService] = None


def get_metrics_service() -> MetricsService:
    """MetricsService 인스턴스 반환"""
    global _metrics_service
    if _metrics_service is None:
        _metrics_service = MetricsService(MetricsClient())
    return _metrics_service


@router.get(
    "/functions/{service_name}",
    response_model=FunctionMetrics,
    summary="함수 통합 메트릭 조회",
    description="Knative 서비스의 Pod, 동시성, 요청 처리 메트릭을 통합하여 반환합니다.",
)
async def get_function_metrics(
    service_name: str,
    namespace: str = Query(default="default", description="Kubernetes 네임스페이스"),
    service: MetricsService = Depends(get_metrics_service),
) -> FunctionMetrics:
    """
    함수 통합 메트릭 조회

    Args:
        service_name: Knative 서비스 이름
        namespace: Kubernetes 네임스페이스 (기본값: default)

    Returns:
        FunctionMetrics: 통합 메트릭 정보
    """
    try:
        return await service.get_function_metrics(service_name, namespace)
    except MetricsServiceError as e:
        logger.error(f"Failed to get function metrics: {e}")
        raise HTTPException(status_code=503, detail=f"Metrics unavailable: {e}")


@router.get(
    "/functions/{service_name}/pods",
    response_model=PodMetrics,
    summary="Pod 메트릭 조회",
    description="현재/원하는/대기 중인 Pod 수를 반환합니다.",
)
async def get_pod_metrics(
    service_name: str,
    namespace: str = Query(default="default", description="Kubernetes 네임스페이스"),
    service: MetricsService = Depends(get_metrics_service),
) -> PodMetrics:
    """
    Pod 관련 메트릭만 조회

    Args:
        service_name: Knative 서비스 이름
        namespace: Kubernetes 네임스페이스

    Returns:
        PodMetrics: Pod 메트릭 정보
    """
    try:
        return await service.get_pod_metrics(service_name, namespace)
    except MetricsServiceError as e:
        logger.error(f"Failed to get pod metrics: {e}")
        raise HTTPException(status_code=503, detail=f"Metrics unavailable: {e}")


@router.get(
    "/functions/{service_name}/concurrency",
    response_model=ConcurrencyMetrics,
    summary="동시성 메트릭 조회",
    description="목표/안정적 동시성 및 패닉 모드 상태를 반환합니다.",
)
async def get_concurrency_metrics(
    service_name: str,
    namespace: str = Query(default="default", description="Kubernetes 네임스페이스"),
    service: MetricsService = Depends(get_metrics_service),
) -> ConcurrencyMetrics:
    """
    동시성 관련 메트릭만 조회

    Args:
        service_name: Knative 서비스 이름
        namespace: Kubernetes 네임스페이스

    Returns:
        ConcurrencyMetrics: 동시성 메트릭 정보
    """
    try:
        return await service.get_concurrency_metrics(service_name, namespace)
    except MetricsServiceError as e:
        logger.error(f"Failed to get concurrency metrics: {e}")
        raise HTTPException(status_code=503, detail=f"Metrics unavailable: {e}")
