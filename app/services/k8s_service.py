import logging
import uuid
from typing import Dict, Optional

from kubernetes import client
from sqlalchemy.orm import Session

from app.config import settings
from app.core.k8s_client import K8sClient, K8sClientError
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
        self.k8s_client = K8sClient()

    def deploy_function(
        self,
        function: Function,
        workspace: Workspace,
        custom_path: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        함수 배포 전체 워크플로우 실행

        Args:
            function: 배포할 함수 객체
            workspace: 워크스페이스 객체
            custom_path: 사용자 정의 경로
            env_vars: 추가 환경변수 (선택사항)

        Returns:
            배포 결과 정보 (namespace, service_name, ingress_url)

        Raises:
            K8sServiceError: 배포 중 오류 발생 시
        """
        try:
            # 1. Namespace 생성
            namespace_name = self._generate_namespace_name(
                workspace.name, str(function.id)
            )
            namespace_labels = {
                "app": "runna",
                "workspace": workspace.name,
                "function-id": str(function.id),
            }

            namespace = self.k8s_client.create_namespace(
                name=namespace_name, labels=namespace_labels
            )

            # 2. KNative Service 배포
            knative_manifest = self._build_knative_manifest(
                function=function,
                namespace=namespace,
                env_vars=env_vars,
            )

            service_name = self.k8s_client.create_knative_service(
                namespace=namespace, manifest=knative_manifest
            )

            # 3. Ingress 생성
            ingress_manifest = self._build_ingress_manifest(
                workspace_name=workspace.name,
                custom_path=custom_path,
                service_name=service_name,
                namespace=namespace,
            )

            ingress_name = self.k8s_client.create_ingress(
                namespace=namespace, manifest=ingress_manifest
            )

            # 4. URL 생성
            ingress_url = self._generate_ingress_url(workspace.name, custom_path)

            result = {
                "namespace": namespace,
                "service_name": service_name,
                "ingress_name": ingress_name,
                "ingress_url": ingress_url,
            }

            logger.info(
                f"🚀 Function {function.name} deployed successfully: {ingress_url}"
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
        namespace_name = self._generate_namespace_name(workspace.name, str(function.id))

        try:
            # Namespace 삭제 (관련된 모든 리소스가 함께 삭제됨)
            success = self.k8s_client.delete_namespace(namespace_name)

            if success:
                logger.info(
                    f"🧹 Function {function.name} resources cleaned up successfully"
                )

            return success

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
        namespace_name = self._generate_namespace_name(workspace.name, str(function.id))

        return self.k8s_client.get_knative_service_status(
            namespace=namespace_name, service_name=function.name
        )

    def _generate_namespace_name(self, workspace_name: str, function_id: str) -> str:
        """Namespace 이름 생성"""
        return f"{settings.k8s_namespace_prefix}-{workspace_name}-{function_id}"

    def _generate_ingress_url(self, workspace_name: str, custom_path: str) -> str:
        """Ingress URL 생성"""
        subdomain = f"{workspace_name}.{settings.k8s_ingress_domain}"
        return f"https://{subdomain}{custom_path}"

    def _build_knative_manifest(
        self,
        function: Function,
        namespace: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict:
        """KNative Service 매니페스트 생성"""
        revision_name = f"{function.name}-{uuid.uuid4().hex[:8]}"

        # 환경변수 설정
        env_list = [{"name": "CODE_CONTENT", "value": function.code}]
        if env_vars:
            env_list.extend([{"name": k, "value": v} for k, v in env_vars.items()])

        return {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "name": function.name,
                "namespace": namespace,
                "labels": {
                    "app": "runna",
                    "function": function.name,
                    "function-id": str(function.id),
                },
            },
            "spec": {
                "template": {
                    "metadata": {
                        "name": revision_name,
                        "annotations": {
                            "autoscaling.knative.dev/minScale": (
                                settings.knative_min_scale
                            ),
                            "autoscaling.knative.dev/maxScale": (
                                settings.knative_max_scale
                            ),
                        },
                    },
                    "spec": {
                        "containers": [
                            {
                                "name": "user-container",
                                "image": settings.k8s_docker_image,
                                "resources": {
                                    "requests": {
                                        "cpu": settings.k8s_cpu_request,
                                        "memory": settings.k8s_memory_request,
                                    },
                                    "limits": {
                                        "cpu": settings.k8s_cpu_limit,
                                        "memory": settings.k8s_memory_limit,
                                    },
                                },
                                "env": env_list,
                            }
                        ],
                    },
                },
            },
        }

    def _build_ingress_manifest(
        self,
        workspace_name: str,
        custom_path: str,
        service_name: str,
        namespace: str,
    ) -> client.V1Ingress:
        """Ingress 매니페스트 생성"""
        subdomain = f"{workspace_name}.{settings.k8s_ingress_domain}"
        ingress_name = f"{service_name}-ingress"

        return client.V1Ingress(
            metadata=client.V1ObjectMeta(
                name=ingress_name,
                namespace=namespace,
                labels={
                    "app": "runna",
                    "workspace": workspace_name,
                },
                annotations={
                    "kubernetes.io/ingress.class": settings.k8s_ingress_class,
                    "nginx.ingress.kubernetes.io/rewrite-target": "/",
                    "cert-manager.io/cluster-issuer": "letsencrypt-prod",
                },
            ),
            spec=client.V1IngressSpec(
                tls=[
                    client.V1IngressTLS(
                        hosts=[subdomain],
                        secret_name=f"{workspace_name}-tls",
                    )
                ],
                rules=[
                    client.V1IngressRule(
                        host=subdomain,
                        http=client.V1HTTPIngressRuleValue(
                            paths=[
                                client.V1HTTPIngressPath(
                                    path=custom_path,
                                    path_type="Prefix",
                                    backend=client.V1IngressBackend(
                                        service=client.V1IngressServiceBackend(
                                            name=service_name,
                                            port=client.V1ServiceBackendPort(number=80),
                                        )
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
        )
