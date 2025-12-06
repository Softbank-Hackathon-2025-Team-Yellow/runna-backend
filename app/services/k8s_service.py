import logging
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.k8s_client import K8sClient, K8sClientError
from app.core.k8s_manifests import ManifestBuilder
from app.core.sanitize import create_safe_namespace_name
from app.models.function import Function
from app.models.workspace import Workspace

logger = logging.getLogger(__name__)


class K8sServiceError(Exception):
    """K8sService 관련 예외"""

    pass


class K8sService:
    """
    Kubernetes 관련 비즈니스 로직 처리

    K8sClient를 사용하여 함수 배포, 삭제, 상태 확인 등의
    워크플로우를 관리
    """

    def __init__(self, db: Session):
        self.db = db
        try:
            self.k8s_client = K8sClient()
            logger.info("K8sService initialized with real K8sClient")
        except Exception as e:
            logger.warning(f"Failed to initialize K8sClient, using Mock: {e}")
            from app.core.mock_k8s_client import MockK8sClient

            self.k8s_client = MockK8sClient()

    def create_namespace(
        self, workspace_alias: str, function_id: str
    ) -> str:
        """
        Function을 위한 Namespace 생성

        Args:
            workspace_alias: 워크스페이스 별칭
            function_id: 함수 ID

        Returns:
            생성된 namespace 이름

        Raises:
            K8sServiceError: namespace 생성 실패 시
        """
        try:
            namespace_name = create_safe_namespace_name(workspace_alias, function_id)

            namespace_labels = {
                "app": "runna",
                "workspace": workspace_alias,
                "function-id": function_id,
            }

            namespace = self.k8s_client.create_namespace(
                name=namespace_name, labels=namespace_labels
            )
            logger.info(f"Created namespace {namespace} for function {function_id}")
            return namespace

        except K8sClientError as e:
            error_msg = f"Failed to create namespace for function {function_id}: {str(e)}"
            logger.error(error_msg)
            raise K8sServiceError(error_msg)

    def deploy_function(
        self,
        function: Function,
        workspace: Workspace,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        함수 배포 전체 워크플로우 실행

        Args:
            function: 배포할 함수 객체
            workspace: 워크스페이스 객체
            env_vars: 추가 환경변수 (선택사항)

        Returns:
            배포 결과 정보 (namespace, service_name, function_url)

        Raises:
            K8sServiceError: 배포 중 오류 발생 시
        """
        try:
            # 1. Namespace 확인 (이미 create_function에서 생성되었음)
            namespace_name = create_safe_namespace_name(
                workspace.alias, str(function.id)
            )

            # Namespace 존재 여부 확인
            try:
                self.k8s_client.v1_core.read_namespace(name=namespace_name)
                namespace = namespace_name
                logger.info(f"Using existing namespace: {namespace}")
            except Exception:
                # Namespace가 없으면 에러 발생
                raise K8sServiceError(
                    f"Namespace {namespace_name} not found. "
                    "Function must be created before deployment."
                )

            # 2. KNative Service 배포
            try:
                knative_manifest = ManifestBuilder.build_knative_service_manifest(
                    function=function,
                    namespace=namespace,
                    env_vars=env_vars,
                )
            except ValueError as e:
                raise K8sServiceError(str(e))

            service_name = self.k8s_client.create_knative_service(
                namespace=namespace, manifest=knative_manifest
            )

            # 3. ClusterDomainClaim 생성
            subdomain = self._generate_subdomain(workspace.alias)
            claim_name = self.k8s_client.create_cluster_domain_claim(
                domain=subdomain, namespace=namespace
            )

            # 4. DomainMapping 생성
            domain_mapping_name = self.k8s_client.create_domain_mapping(
                namespace=namespace,
                domain=subdomain,
                service_name=service_name,
            )

            # 5. HTTPRoute 생성 (Gateway API)
            http_route_name = self.k8s_client.create_http_route(
                namespace=namespace,
                hostname=subdomain,
                path=function.endpoint,
                service_name=service_name,
                gateway_name=settings.gateway_name,
            )

            # 6. 최종 URL 생성
            function_url = self._generate_function_url(
                workspace.alias, function.endpoint
            )

            result = {
                "namespace": namespace,
                "service_name": service_name,
                "cluster_domain_claim": claim_name,
                "domain_mapping": domain_mapping_name,
                "http_route": http_route_name,
                "function_url": function_url,
            }

            logger.info(
                f"🚀 Function {function.name} deployed successfully: {function_url}"
            )
            return result

        except K8sClientError as e:
            error_msg = f"Failed to deploy function {function.name}: {str(e)}"
            logger.error(error_msg)
            raise K8sServiceError(error_msg)

    def cleanup_function_resources(
        self, function: Function, workspace: Workspace
    ) -> bool:
        """
        함수와 관련된 모든 리소스 정리

        Args:
            function: 정리할 함수 객체
            workspace: 워크스페이스 객체

        Returns:
            정리 성공 여부
        """
        namespace_name = create_safe_namespace_name(workspace.alias, str(function.id))
        subdomain = self._generate_subdomain(workspace.alias)

        try:
            cleanup_success = True

            # 1. ClusterDomainClaim 삭제 (클러스터 수준 리소스)
            try:
                self.k8s_client.delete_cluster_domain_claim(subdomain)
            except Exception as e:
                logger.warning(f"Failed to delete ClusterDomainClaim: {e}")
                cleanup_success = False

            # 2. Namespace 삭제 (네임스페이스 내 모든 리소스가 함께 삭제됨)
            # - DomainMapping, HTTPRoute, KNative Service 등이 모두 삭제됨
            namespace_success = self.k8s_client.delete_namespace(namespace_name)

            if namespace_success and cleanup_success:
                logger.info(
                    f"🧹 Function {function.name} resources cleaned up successfully"
                )
                return True
            else:
                logger.warning(
                    f"Function {function.name} cleanup completed with some warnings"
                )
                return False

        except Exception as e:
            logger.error(
                f"Failed to cleanup function {function.name} resources: {str(e)}"
            )
            return False

    def get_function_status(
        self, function: Function, workspace: Workspace
    ) -> Optional[Dict]:
        """
        함수 배포 상태 확인

        Args:
            function: 상태를 확인할 함수 객체
            workspace: 워크스페이스 객체

        Returns:
            함수 상태 정보 또는 None
        """
        namespace_name = create_safe_namespace_name(workspace.alias, str(function.id))

        return self.k8s_client.get_knative_service_status(
            namespace=namespace_name, service_name=function.name
        )

    def _generate_subdomain(self, workspace_alias: str) -> str:
        """서브도메인 생성"""
        return f"{workspace_alias}.{settings.base_domain}"

    def _generate_function_url(self, workspace_alias: str, endpoint: str) -> str:
        """함수 최종 URL 생성"""
        subdomain = self._generate_subdomain(workspace_alias)
        return f"https://{subdomain}{endpoint}"

