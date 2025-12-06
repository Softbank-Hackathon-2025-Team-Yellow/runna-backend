"""
메트릭 수집 로직 테스트

MetricsClient, MetricsService, API 엔드포인트 테스트
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.infra.metrics_client import MetricsClient, MetricsClientError
from app.schemas.metrics import (
    ConcurrencyMetrics,
    FunctionMetrics,
    PodMetrics,
    RequestMetrics,
)
from app.services.metrics_service import MetricsService, MetricsServiceError


# ============================================================
# MetricsClient 테스트
# ============================================================


class TestMetricsClient:
    """MetricsClient 단위 테스트"""

    @pytest.fixture
    def client(self):
        return MetricsClient(base_url="http://test-prometheus:9090")

    @pytest.mark.asyncio
    async def test_query_success(self, client):
        """성공적인 쿼리 응답 테스트"""
        mock_response = {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [
                    {
                        "metric": {"kn_service_name": "test-service"},
                        "value": [1764815755.454, "1"],
                    }
                ],
            },
        }

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(
                return_value=MagicMock(
                    json=lambda: mock_response, raise_for_status=lambda: None
                )
            )
            mock_get_client.return_value = mock_http

            result = await client.query('kn_revision_pods_count{kn_service_name="test"}')

            assert result["status"] == "success"
            assert result["data"]["resultType"] == "vector"
            assert len(result["data"]["result"]) == 1

    @pytest.mark.asyncio
    async def test_query_failure_status(self, client):
        """실패 상태 응답 테스트"""
        mock_response = {"status": "error", "error": "bad_query"}

        with patch.object(client, "_get_client") as mock_get_client:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(
                return_value=MagicMock(
                    json=lambda: mock_response, raise_for_status=lambda: None
                )
            )
            mock_get_client.return_value = mock_http

            with pytest.raises(MetricsClientError):
                await client.query("invalid_query")


# ============================================================
# MetricsService 테스트
# ============================================================


class TestMetricsService:
    """MetricsService 단위 테스트"""

    @pytest.fixture
    def mock_client(self):
        return AsyncMock(spec=MetricsClient)

    @pytest.fixture
    def service(self, mock_client):
        return MetricsService(metrics_client=mock_client)

    def _make_prometheus_response(self, value: str):
        """Prometheus 응답 Mock 생성"""
        return {
            "status": "success",
            "data": {
                "resultType": "vector",
                "result": [{"metric": {}, "value": [1764815755.454, value]}],
            },
        }

    @pytest.mark.asyncio
    async def test_get_pod_metrics(self, service, mock_client):
        """Pod 메트릭 조회 테스트"""
        # current, desired, pending 순서로 응답
        mock_client.query.side_effect = [
            self._make_prometheus_response("3"),  # current
            self._make_prometheus_response("5"),  # desired
            self._make_prometheus_response("2"),  # pending
        ]

        result = await service.get_pod_metrics("test-service", "default")

        assert isinstance(result, PodMetrics)
        assert result.current_count == 3
        assert result.desired_count == 5
        assert result.pending_count == 2

    @pytest.mark.asyncio
    async def test_get_concurrency_metrics(self, service, mock_client):
        """동시성 메트릭 조회 테스트"""
        mock_client.query.side_effect = [
            self._make_prometheus_response("100"),  # target
            self._make_prometheus_response("50"),  # stable
            self._make_prometheus_response("0"),  # panic_mode (0 = False)
        ]

        result = await service.get_concurrency_metrics("test-service", "default")

        assert isinstance(result, ConcurrencyMetrics)
        assert result.target == 100.0
        assert result.stable == 50.0
        assert result.panic_mode is False

    @pytest.mark.asyncio
    async def test_get_concurrency_metrics_panic_mode_true(self, service, mock_client):
        """패닉 모드 활성화 테스트"""
        mock_client.query.side_effect = [
            self._make_prometheus_response("100"),
            self._make_prometheus_response("50"),
            self._make_prometheus_response("1"),  # panic_mode (1 = True)
        ]

        result = await service.get_concurrency_metrics("test-service", "default")

        assert result.panic_mode is True

    @pytest.mark.asyncio
    async def test_get_request_metrics(self, service, mock_client):
        """요청 처리 메트릭 조회 테스트"""
        mock_client.query.side_effect = [
            self._make_prometheus_response("100"),  # count
            self._make_prometheus_response("5.0"),  # sum
        ]

        result = await service.get_request_metrics("test-service", "default")

        assert isinstance(result, RequestMetrics)
        assert result.total_count == 100
        assert result.avg_duration_seconds == 0.05  # 5.0 / 100

    @pytest.mark.asyncio
    async def test_get_request_metrics_no_data(self, service, mock_client):
        """요청 데이터 없음 테스트"""
        mock_client.query.return_value = {
            "status": "success",
            "data": {"resultType": "vector", "result": []},
        }

        result = await service.get_request_metrics("test-service", "default")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_function_metrics(self, service, mock_client):
        """통합 메트릭 조회 테스트"""
        mock_client.query.side_effect = [
            # Pod metrics
            self._make_prometheus_response("2"),  # current
            self._make_prometheus_response("2"),  # desired
            self._make_prometheus_response("0"),  # pending
            # Concurrency metrics
            self._make_prometheus_response("100"),  # target
            self._make_prometheus_response("50"),  # stable
            self._make_prometheus_response("0"),  # panic_mode
            # Request metrics
            self._make_prometheus_response("50"),  # count
            self._make_prometheus_response("2.5"),  # sum
            # Capacity excess
            self._make_prometheus_response("0"),
        ]

        result = await service.get_function_metrics("test-service", "default")

        assert isinstance(result, FunctionMetrics)
        assert result.service_name == "test-service"
        assert result.namespace == "default"
        assert result.pods.current_count == 2
        assert result.concurrency.target == 100.0
        assert result.requests.total_count == 50
        assert result.capacity_excess == 0.0
        assert isinstance(result.timestamp, datetime)


# ============================================================
# 스키마 테스트
# ============================================================


class TestMetricsSchemas:
    """메트릭 스키마 테스트"""

    def test_pod_metrics_creation(self):
        """PodMetrics 생성 테스트"""
        metrics = PodMetrics(current_count=3, desired_count=5, pending_count=1)

        assert metrics.current_count == 3
        assert metrics.desired_count == 5
        assert metrics.pending_count == 1

    def test_pod_metrics_defaults(self):
        """PodMetrics 기본값 테스트"""
        metrics = PodMetrics(current_count=1, desired_count=1)

        assert metrics.pending_count == 0

    def test_function_metrics_creation(self):
        """FunctionMetrics 생성 테스트"""
        metrics = FunctionMetrics(
            service_name="test-service",
            namespace="default",
            pods=PodMetrics(current_count=1, desired_count=1),
            concurrency=ConcurrencyMetrics(target=100, stable=50, panic_mode=False),
            capacity_excess=0.0,
            timestamp=datetime.now(timezone.utc),
        )

        assert metrics.service_name == "test-service"
        assert metrics.pods.current_count == 1
        assert metrics.requests is None  # Optional field

    def test_function_metrics_json_serialization(self):
        """JSON 직렬화 테스트"""
        metrics = FunctionMetrics(
            service_name="test-service",
            namespace="default",
            pods=PodMetrics(current_count=1, desired_count=1),
            concurrency=ConcurrencyMetrics(target=100, stable=50, panic_mode=False),
            capacity_excess=0.0,
            timestamp=datetime.now(timezone.utc),
        )

        json_data = metrics.model_dump()

        assert json_data["service_name"] == "test-service"
        assert "pods" in json_data
        assert "concurrency" in json_data
