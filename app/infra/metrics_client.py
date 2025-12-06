"""
Prometheus HTTP API 클라이언트

k3s 클러스터 내 Prometheus에서 Knative 메트릭을 수집합니다.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class MetricsClientError(Exception):
    """MetricsClient 관련 예외"""

    pass


class MetricsClient:
    """
    Prometheus HTTP API 클라이언트

    GET /api/v1/query?query={promql} 호출을 담당합니다.
    """

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.prometheus_url
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """HTTP 클라이언트 인스턴스 반환 (lazy initialization)"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=httpx.Timeout(10.0),
            )
        return self._client

    async def query(self, promql: str) -> Dict[str, Any]:
        """
        PromQL 쿼리 실행

        Args:
            promql: PromQL 쿼리 문자열
                예: kn_revision_pods_count{kn_service_name="my-service",k8s_namespace_name="default"}

        Returns:
            Prometheus API 응답 (dict)
            {
                "status": "success",
                "data": {
                    "resultType": "vector",
                    "result": [...]
                }
            }

        Raises:
            MetricsClientError: API 호출 실패 시
        """
        client = await self._get_client()

        try:
            response = await client.get(
                "/api/v1/query",
                params={"query": promql},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise MetricsClientError(
                    f"Prometheus query failed: {data.get('error', 'Unknown error')}"
                )

            return data

        except httpx.TimeoutException as e:
            logger.error(f"Prometheus query timeout: {promql}")
            raise MetricsClientError(f"Query timeout: {e}") from e
        except httpx.HTTPStatusError as e:
            logger.error(f"Prometheus HTTP error: {e.response.status_code}")
            raise MetricsClientError(f"HTTP error: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Prometheus query error: {e}")
            raise MetricsClientError(f"Query failed: {e}") from e

    async def query_range(
        self, promql: str, start: str, end: str, step: str
    ) -> Dict[str, Any]:
        """
        범위 쿼리 실행 (선택적)

        Args:
            promql: PromQL 쿼리 문자열
            start: 시작 시간 (Unix timestamp 또는 RFC3339)
            end: 종료 시간
            step: 간격 (예: "15s", "1m")

        Returns:
            Prometheus API 응답 (matrix 타입)
        """
        client = await self._get_client()

        try:
            response = await client.get(
                "/api/v1/query_range",
                params={
                    "query": promql,
                    "start": start,
                    "end": end,
                    "step": step,
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "success":
                raise MetricsClientError(
                    f"Prometheus range query failed: {data.get('error', 'Unknown error')}"
                )

            return data

        except Exception as e:
            logger.error(f"Prometheus range query error: {e}")
            raise MetricsClientError(f"Range query failed: {e}") from e

    async def close(self):
        """HTTP 클라이언트 정리"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
