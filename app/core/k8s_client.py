import logging
import uuid
from typing import Dict, Optional

from kubernetes import client, config
from kubernetes.client import ApiException

from app.config import settings

logger = logging.getLogger(__name__)


class K8sClientError(Exception):
    """K8sClient 관련 예외"""

    pass


class K8sClient:
    """
    Kubernetes 클라이언트

    Namespace 생성, KNative 함수 배포, Ingress 설정 등
    Kubernetes 리소스 관리를 담당
    """

    def __init__(self):
        """Kubernetes 클라이언트 초기화"""
        try:
            # 클러스터 내부에서 실행되는 경우
            config.load_incluster_config()
            logger.info("✅ Loaded In-Cluster Config")
        except config.ConfigException:
            try:
                # 로컬에서 실행되는 경우
                config.load_kube_config()
                logger.info("✅ Loaded Kube Config")
            except config.ConfigException as e:
                raise K8sClientError(f"Kubernetes 설정을 로드할 수 없습니다: {e}")

        self.v1_core = client.CoreV1Api()
        self.v1_apps = client.AppsV1Api()
        self.v1_networking = client.NetworkingV1Api()
        self.custom_objects = client.CustomObjectsApi()

        logger.info("K8sClient 초기화 완료")

    def create_namespace(self, workspace_name: str, function_uuid: str) -> str:
        """
        Namespace 생성

        Args:
            workspace_name: 워크스페이스 이름 (alias)
            function_uuid: 함수 UUID

        Returns:
            생성된 namespace 이름

        Raises:
            K8sClientError: namespace 생성 실패 시
        """
        namespace_name = (
            f"{settings.k8s_namespace_prefix}-{workspace_name}-{function_uuid}"
        )

        # 네임스페이스 객체 생성
        namespace_manifest = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels={
                    "app": "runna",
                    "workspace": workspace_name,
                    "function-uuid": function_uuid,
                },
            )
        )

        try:
            # 네임스페이스가 이미 존재하는지 확인
            try:
                self.v1_core.read_namespace(name=namespace_name)
                logger.info(f"Namespace {namespace_name} 이미 존재함")
                return namespace_name
            except ApiException as e:
                if e.status != 404:
                    raise

            # 네임스페이스 생성
            self.v1_core.create_namespace(body=namespace_manifest)
            logger.info(f"✅ Namespace {namespace_name} 생성 완료")
            return namespace_name

        except ApiException as e:
            error_msg = f"Namespace {namespace_name} 생성 실패: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def deploy_knative_function(
        self,
        namespace: str,
        function_name: str,
        code_content: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        KNative Service로 함수 배포

        Args:
            namespace: 배포할 네임스페이스
            function_name: 함수 이름
            code_content: 실행할 코드 내용
            env_vars: 추가 환경변수 (선택사항)

        Returns:
            배포된 KNative Service 이름

        Raises:
            K8sClientError: 배포 실패 시
        """
        revision_name = f"{function_name}-{uuid.uuid4().hex[:8]}"

        # 환경변수 설정
        env_list = [{"name": "CODE_CONTENT", "value": code_content}]
        if env_vars:
            env_list.extend([{"name": k, "value": v} for k, v in env_vars.items()])

        # KNative Service 매니페스트 생성 (reference.py 기반)
        knative_manifest = {
            "apiVersion": "serving.knative.dev/v1",
            "kind": "Service",
            "metadata": {
                "name": function_name,
                "namespace": namespace,
                "labels": {
                    "app": "runna",
                    "function": function_name,
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

        try:
            # KNative Service 배포
            response = self.custom_objects.create_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=namespace,
                plural="services",
                body=knative_manifest,
            )

            service_name = response["metadata"]["name"]
            logger.info(
                f"✅ KNative Service {service_name} 배포 완료 (namespace: {namespace})"
            )
            return service_name

        except ApiException as e:
            error_msg = f"KNative Service {function_name} 배포 실패: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def create_ingress(
        self,
        namespace: str,
        ingress_name: str,
        workspace_name: str,
        custom_path: str,
        service_name: str,
        service_port: int = 80,
    ) -> str:
        """
        Ingress 리소스 생성하여 외부 URL 라우팅 설정

        Args:
            namespace: Ingress가 생성될 네임스페이스
            ingress_name: Ingress 리소스 이름
            workspace_name: 워크스페이스 이름 (subdomain으로 사용)
            custom_path: 사용자 정의 경로
            service_name: 라우팅할 서비스 이름
            service_port: 서비스 포트 (기본값: 80)

        Returns:
            생성된 Ingress URL

        Raises:
            K8sClientError: Ingress 생성 실패 시
        """
        subdomain = f"{workspace_name}.{settings.k8s_ingress_domain}"
        full_url = f"https://{subdomain}{custom_path}"

        # Ingress 매니페스트 생성
        ingress_manifest = client.V1Ingress(
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
                                            port=client.V1ServiceBackendPort(
                                                number=service_port
                                            ),
                                        )
                                    ),
                                )
                            ]
                        ),
                    )
                ],
            ),
        )

        try:
            # Ingress 생성
            response = self.v1_networking.create_namespaced_ingress(
                namespace=namespace, body=ingress_manifest
            )

            ingress_name = response.metadata.name
            logger.info(f"✅ Ingress {ingress_name} 생성 완료")
            logger.info(f"📡 URL: {full_url}")
            return full_url

        except ApiException as e:
            error_msg = f"Ingress {ingress_name} 생성 실패: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_namespace(self, namespace_name: str) -> bool:
        """
        Namespace 삭제 (관련된 모든 리소스 함께 삭제됨)

        Args:
            namespace_name: 삭제할 네임스페이스 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.v1_core.delete_namespace(name=namespace_name)
            logger.info(f"✅ Namespace {namespace_name} 삭제 완료")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"Namespace {namespace_name} 이미 삭제됨 또는 존재하지 않음"
                )
                return True
            error_msg = f"Namespace {namespace_name} 삭제 실패: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_knative_service(self, namespace: str, service_name: str) -> bool:
        """
        KNative Service 삭제

        Args:
            namespace: 서비스가 위치한 네임스페이스
            service_name: 삭제할 서비스 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.custom_objects.delete_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=namespace,
                plural="services",
                name=service_name,
            )
            logger.info(f"✅ KNative Service {service_name} 삭제 완료")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"KNative Service {service_name} 이미 삭제됨 또는 존재하지 않음"
                )
                return True
            error_msg = f"KNative Service {service_name} 삭제 실패: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_ingress(self, namespace: str, ingress_name: str) -> bool:
        """
        Ingress 리소스 삭제

        Args:
            namespace: Ingress가 위치한 네임스페이스
            ingress_name: 삭제할 Ingress 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.v1_networking.delete_namespaced_ingress(
                namespace=namespace, name=ingress_name
            )
            logger.info(f"✅ Ingress {ingress_name} 삭제 완료")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Ingress {ingress_name} 이미 삭제됨 또는 존재하지 않음")
                return True
            error_msg = f"Ingress {ingress_name} 삭제 실패: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def get_namespace_status(self, namespace_name: str) -> Optional[str]:
        """
        Namespace 상태 확인

        Args:
            namespace_name: 확인할 네임스페이스 이름

        Returns:
            네임스페이스 상태 ("Active", "Terminating", None if not found)
        """
        try:
            namespace = self.v1_core.read_namespace(name=namespace_name)
            return namespace.status.phase
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"Namespace {namespace_name} 상태 확인 실패: {e.reason}")
            return None

    def get_knative_service_status(
        self, namespace: str, service_name: str
    ) -> Optional[Dict]:
        """
        KNative Service 상태 확인

        Args:
            namespace: 서비스가 위치한 네임스페이스
            service_name: 확인할 서비스 이름

        Returns:
            서비스 상태 정보 또는 None
        """
        try:
            service = self.custom_objects.get_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=namespace,
                plural="services",
                name=service_name,
            )
            return {
                "ready": service.get("status", {})
                .get("conditions", [{}])[-1]
                .get("status")
                == "True",
                "url": service.get("status", {}).get("url"),
                "conditions": service.get("status", {}).get("conditions", []),
            }
        except ApiException as e:
            if e.status == 404:
                return None
            logger.error(f"KNative Service {service_name} 상태 확인 실패: {e.reason}")
            return None

    def deploy_complete_function(
        self,
        workspace_name: str,
        function_uuid: str,
        function_name: str,
        code_content: str,
        custom_path: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        함수 배포 전체 워크플로우 실행

        1. Namespace 생성
        2. KNative Service 배포
        3. Ingress 생성

        Args:
            workspace_name: 워크스페이스 이름 (alias)
            function_uuid: 함수 UUID
            function_name: 함수 이름
            code_content: 실행할 코드 내용
            custom_path: 사용자 정의 경로
            env_vars: 추가 환경변수 (선택사항)

        Returns:
            배포 결과 정보 (namespace, service_name, ingress_url)

        Raises:
            K8sClientError: 배포 중 오류 발생 시
        """
        try:
            # 1. Namespace 생성
            namespace = self.create_namespace(workspace_name, function_uuid)

            # 2. KNative Service 배포
            service_name = self.deploy_knative_function(
                namespace=namespace,
                function_name=function_name,
                code_content=code_content,
                env_vars=env_vars,
            )

            # 3. Ingress 생성
            ingress_name = f"{function_name}-ingress"
            ingress_url = self.create_ingress(
                namespace=namespace,
                ingress_name=ingress_name,
                workspace_name=workspace_name,
                custom_path=custom_path,
                service_name=service_name,
            )

            result = {
                "namespace": namespace,
                "service_name": service_name,
                "ingress_url": ingress_url,
                "ingress_name": ingress_name,
            }

            logger.info(f"🚀 함수 {function_name} 배포 완료: {ingress_url}")
            return result

        except Exception as e:
            error_msg = f"함수 {function_name} 배포 실패: {str(e)}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def cleanup_function_resources(
        self, workspace_name: str, function_uuid: str, function_name: str
    ) -> bool:
        """
        함수와 관련된 모든 리소스 정리

        Args:
            workspace_name: 워크스페이스 이름
            function_uuid: 함수 UUID
            function_name: 함수 이름

        Returns:
            정리 성공 여부
        """
        namespace = f"{settings.k8s_namespace_prefix}-{workspace_name}-{function_uuid}"

        try:
            # Namespace 삭제 (관련된 모든 리소스가 함께 삭제됨)
            success = self.delete_namespace(namespace)

            if success:
                logger.info(f"🧹 함수 {function_name} 리소스 정리 완료")

            return success

        except Exception as e:
            logger.error(f"함수 {function_name} 리소스 정리 실패: {str(e)}")
            return False
