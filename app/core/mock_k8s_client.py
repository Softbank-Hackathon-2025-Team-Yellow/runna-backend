import logging
from typing import Dict, Optional

from kubernetes import client

logger = logging.getLogger(__name__)


class MockK8sClientError(Exception):
    """MockK8sClient 관련 예외"""

    pass


class MockK8sClient:
    """
    테스트용 Mock Kubernetes API 클라이언트

    K8sClient와 동일한 인터페이스를 제공하지만 실제 Kubernetes API를
    호출하지 않고 시뮬레이션된 응답을 반환
    """

    def __init__(self):
        """Mock Kubernetes 클라이언트 초기화"""
        logger.info("MockK8sClient initialized (test mode)")

    def create_namespace(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Mock Namespace 생성

        Args:
            name: 생성할 namespace 이름
            labels: 네임스페이스 라벨 (선택사항)

        Returns:
            생성된 namespace 이름
        """
        logger.info(f"[MOCK] ✅ Namespace {name} created successfully")
        return name

    def create_knative_service(self, namespace: str, manifest: Dict) -> str:
        """
        Mock KNative Service 생성 또는 업데이트

        Args:
            namespace: 배포할 네임스페이스
            manifest: KNative Service 매니페스트

        Returns:
            생성/업데이트된 KNative Service 이름
        """
        service_name = manifest.get("metadata", {}).get("name", "mock-service")
        logger.info(
            f"[MOCK] ✅ KNative Service {service_name} created/updated successfully "
            f"(namespace: {namespace})"
        )
        return service_name

    def create_ingress(self, namespace: str, manifest: client.V1Ingress) -> str:
        """
        Mock Ingress 리소스 생성

        Args:
            namespace: Ingress가 생성될 네임스페이스
            manifest: Ingress 매니페스트

        Returns:
            생성된 Ingress 이름
        """
        ingress_name = manifest.metadata.name if manifest.metadata else "mock-ingress"
        logger.info(f"[MOCK] ✅ Ingress {ingress_name} created successfully")
        return ingress_name

    def delete_namespace(self, name: str) -> bool:
        """
        Mock Namespace 삭제

        Args:
            name: 삭제할 네임스페이스 이름

        Returns:
            삭제 성공 여부
        """
        logger.info(f"[MOCK] ✅ Namespace {name} deleted successfully")
        return True

    def delete_knative_service(self, namespace: str, service_name: str) -> bool:
        """
        Mock KNative Service 삭제

        Args:
            namespace: 서비스가 위치한 네임스페이스
            service_name: 삭제할 서비스 이름

        Returns:
            삭제 성공 여부
        """
        logger.info(f"[MOCK] ✅ KNative Service {service_name} deleted successfully")
        return True

    def delete_ingress(self, namespace: str, ingress_name: str) -> bool:
        """
        Mock Ingress 리소스 삭제

        Args:
            namespace: Ingress가 위치한 네임스페이스
            ingress_name: 삭제할 Ingress 이름

        Returns:
            삭제 성공 여부
        """
        logger.info(f"[MOCK] ✅ Ingress {ingress_name} deleted successfully")
        return True

    def get_namespace_status(self, namespace_name: str) -> Optional[str]:
        """
        Mock Namespace 상태 확인

        Args:
            namespace_name: 확인할 네임스페이스 이름

        Returns:
            네임스페이스 상태 ("Active", "Terminating", None if not found)
        """
        logger.info(f"[MOCK] Checking namespace {namespace_name} status")
        return "Active"

    def get_knative_service_status(
        self, namespace: str, service_name: str
    ) -> Optional[Dict]:
        """
        Mock KNative Service 상태 확인

        Args:
            namespace: 서비스가 위치한 네임스페이스
            service_name: 확인할 서비스 이름

        Returns:
            서비스 상태 정보
        """
        logger.info(f"[MOCK] Checking KNative Service {service_name} status")
        return {
            "ready": True,
            "url": f"http://{service_name}.{namespace}.example.com",
            "conditions": [
                {
                    "type": "Ready",
                    "status": "True",
                    "reason": "MockReady",
                    "message": "Mock service is ready",
                }
            ],
        }

    def create_cluster_domain_claim(self, domain: str, namespace: str) -> str:
        """
        Mock ClusterDomainClaim 생성

        Args:
            domain: 클레임할 도메인
            namespace: 도메인을 사용할 네임스페이스

        Returns:
            생성된 ClusterDomainClaim 이름
        """
        logger.info(f"[MOCK] ✅ ClusterDomainClaim {domain} created successfully")
        return domain

    def delete_cluster_domain_claim(self, claim_name: str) -> bool:
        """
        Mock ClusterDomainClaim 삭제

        Args:
            claim_name: 삭제할 클레임 이름

        Returns:
            삭제 성공 여부
        """
        logger.info(f"[MOCK] ✅ ClusterDomainClaim {claim_name} deleted successfully")
        return True

    def create_domain_mapping(
        self, namespace: str, domain: str, service_name: str
    ) -> str:
        """
        Mock DomainMapping 생성

        Args:
            namespace: DomainMapping이 생성될 네임스페이스
            domain: 매핑할 도메인
            service_name: 연결할 KNative Service 이름

        Returns:
            생성된 DomainMapping 이름
        """
        logger.info(f"[MOCK] ✅ DomainMapping {domain} created successfully")
        return domain

    def delete_domain_mapping(self, namespace: str, mapping_name: str) -> bool:
        """
        Mock DomainMapping 삭제

        Args:
            namespace: DomainMapping이 위치한 네임스페이스
            mapping_name: 삭제할 DomainMapping 이름

        Returns:
            삭제 성공 여부
        """
        logger.info(f"[MOCK] ✅ DomainMapping {mapping_name} deleted successfully")
        return True

    def create_http_route(
        self,
        namespace: str,
        hostname: str,
        path: str,
        service_name: str,
        gateway_name: str = "3scale-kourier-gateway",
    ) -> str:
        """
        Mock Gateway API HTTPRoute 생성 또는 업데이트

        Args:
            namespace: HTTPRoute가 생성될 네임스페이스
            hostname: 라우팅할 호스트명
            path: 라우팅할 경로
            service_name: 백엔드 KNative Service 이름
            gateway_name: Gateway 이름

        Returns:
            생성/업데이트된 HTTPRoute 이름
        """
        route_name = f"route-{service_name}"
        logger.info(f"[MOCK] ✅ HTTPRoute {route_name} created/updated successfully")
        return route_name

    def delete_http_route(self, namespace: str, route_name: str) -> bool:
        """
        Mock HTTPRoute 삭제

        Args:
            namespace: HTTPRoute가 위치한 네임스페이스
            route_name: 삭제할 HTTPRoute 이름

        Returns:
            삭제 성공 여부
        """
        logger.info(f"[MOCK] ✅ HTTPRoute {route_name} deleted successfully")
        return True

    @property
    def v1_core(self):
        """Mock CoreV1Api 속성"""
        return self

    def read_namespace(self, name: str):
        """Mock namespace 읽기"""
        logger.info(f"[MOCK] Reading namespace {name}")
        return type('MockNamespace', (), {'metadata': {'name': name}})()
