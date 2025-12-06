"""
메트릭 수집 서비스

Prometheus API를 통해 Knative 서비스 메트릭을 조회합니다.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.infra.metrics_client import MetricsClient, MetricsClientError
from app.schemas.metrics import (
    ConcurrencyMetrics,
    FunctionMetrics,
    PodMetrics,
    RequestMetrics,
)

logger = logging.getLogger(__name__)


class MetricsServiceError(Exception):
    """MetricsService 관련 예외"""

    pass


class MetricsService:
    """
    Knative 메트릭 조회 서비스

    Prometheus API를 호출하여 함수 메트릭을 수집합니다.
    """

    def __init__(self, metrics_client: Optional[MetricsClient] = None):
        self.client = metrics_client or MetricsClient()

    def _build_promql(
        self, metric_name: str, service_name: str, namespace: str
    ) -> str:
        """PromQL 쿼리 문자열 생성"""
        return f'{metric_name}{{kn_service_name="{service_name}",k8s_namespace_name="{namespace}"}}'

    def _extract_value(self, result: Dict[str, Any]) -> Optional[float]:
        """
        Prometheus 응답에서 값 추출

        Vector 타입 응답: data.result[0].value[1]
        """
        try:
            results = result.get("data", {}).get("result", [])
            if not results:
                return None
            # value = [timestamp, "값"]
            value_str = results[0].get("value", [None, None])[1]
            return float(value_str) if value_str else None
        except (IndexError, ValueError, TypeError):
            return None

    async def get_pod_metrics(
        self, service_name: str, namespace: str
    ) -> PodMetrics:
        """
        Pod 관련 메트릭 조회

        Args:
            service_name: Knative 서비스 이름
            namespace: Kubernetes 네임스페이스

        Returns:
            PodMetrics 객체
        """
        try:
            # 현재 Pod 수
            current_query = self._build_promql(
                "kn_revision_pods_count", service_name, namespace
            )
            current_result = await self.client.query(current_query)
            current_count = self._extract_value(current_result) or 0

            # 원하는 Pod 수
            desired_query = self._build_promql(
                "kn_revision_pods_desired", service_name, namespace
            )
            desired_result = await self.client.query(desired_query)
            desired_count = self._extract_value(desired_result) or 0

            # 대기 중인 Pod 수
            pending_query = self._build_promql(
                "kn_revision_pods_pending_count", service_name, namespace
            )
            pending_result = await self.client.query(pending_query)
            pending_count = self._extract_value(pending_result) or 0

            return PodMetrics(
                current_count=int(current_count),
                desired_count=int(desired_count),
                pending_count=int(pending_count),
            )

        except MetricsClientError as e:
            logger.error(f"Failed to get pod metrics: {e}")
            raise MetricsServiceError(f"Pod metrics query failed: {e}") from e

    async def get_concurrency_metrics(
        self, service_name: str, namespace: str
    ) -> ConcurrencyMetrics:
        """
        동시성 관련 메트릭 조회

        Args:
            service_name: Knative 서비스 이름
            namespace: Kubernetes 네임스페이스

        Returns:
            ConcurrencyMetrics 객체
        """
        try:
            # 목표 동시성
            target_query = self._build_promql(
                "kn_revision_concurrency_target", service_name, namespace
            )
            target_result = await self.client.query(target_query)
            target = self._extract_value(target_result) or 0.0

            # 안정적 동시성
            stable_query = self._build_promql(
                "kn_revision_concurrency_stable", service_name, namespace
            )
            stable_result = await self.client.query(stable_query)
            stable = self._extract_value(stable_result) or 0.0

            # 패닉 모드
            panic_query = self._build_promql(
                "kn_revision_panic_mode", service_name, namespace
            )
            panic_result = await self.client.query(panic_query)
            panic_mode = (self._extract_value(panic_result) or 0) == 1

            return ConcurrencyMetrics(
                target=target,
                stable=stable,
                panic_mode=panic_mode,
            )

        except MetricsClientError as e:
            logger.error(f"Failed to get concurrency metrics: {e}")
            raise MetricsServiceError(f"Concurrency metrics query failed: {e}") from e

    async def get_request_metrics(
        self, service_name: str, namespace: str
    ) -> Optional[RequestMetrics]:
        """
        요청 처리 메트릭 조회

        Args:
            service_name: Knative 서비스 이름
            namespace: Kubernetes 네임스페이스

        Returns:
            RequestMetrics 객체 또는 None (데이터 없음)
        """
        try:
            # 총 요청 수
            count_query = self._build_promql(
                "kn_queueproxy_app_duration_seconds_count", service_name, namespace
            )
            count_result = await self.client.query(count_query)
            total_count = self._extract_value(count_result)

            if total_count is None:
                return None

            # 평균 처리 시간 (sum / count)
            sum_query = self._build_promql(
                "kn_queueproxy_app_duration_seconds_sum", service_name, namespace
            )
            sum_result = await self.client.query(sum_query)
            total_sum = self._extract_value(sum_result) or 0

            avg_duration = total_sum / total_count if total_count > 0 else None

            return RequestMetrics(
                total_count=int(total_count),
                avg_duration_seconds=avg_duration,
            )

        except MetricsClientError as e:
            logger.warning(f"Failed to get request metrics (optional): {e}")
            return None

    async def get_function_metrics(
        self, service_name: str, namespace: str
    ) -> FunctionMetrics:
        """
        함수 통합 메트릭 조회

        모든 메트릭을 수집하여 FunctionMetrics 객체로 반환합니다.

        Args:
            service_name: Knative 서비스 이름
            namespace: Kubernetes 네임스페이스

        Returns:
            FunctionMetrics 객체
        """
        pods = await self.get_pod_metrics(service_name, namespace)
        concurrency = await self.get_concurrency_metrics(service_name, namespace)
        requests = await self.get_request_metrics(service_name, namespace)

        # 초과 용량
        try:
            excess_query = self._build_promql(
                "kn_revision_capacity_excess", service_name, namespace
            )
            excess_result = await self.client.query(excess_query)
            capacity_excess = self._extract_value(excess_result) or 0.0
        except MetricsClientError:
            capacity_excess = 0.0

        return FunctionMetrics(
            service_name=service_name,
            namespace=namespace,
            pods=pods,
            concurrency=concurrency,
            requests=requests,
            capacity_excess=capacity_excess,
            timestamp=datetime.now(timezone.utc),
        )

    async def close(self):
        """리소스 정리"""
        await self.client.close()
