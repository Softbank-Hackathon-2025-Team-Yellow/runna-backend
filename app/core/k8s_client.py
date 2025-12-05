import logging
from typing import Dict, Optional

from kubernetes import client, config
from kubernetes.client import ApiException

logger = logging.getLogger(__name__)


class K8sClientError(Exception):
    """K8sClient 관련 예외"""

    pass


class K8sClient:
    """
    순수 Kubernetes API 클라이언트

    Kubernetes API 호출만 담당하며 비즈니스 로직은 포함하지 않음
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
                raise K8sClientError(f"Failed to load Kubernetes config: {e}")

        self.v1_core = client.CoreV1Api()
        self.v1_apps = client.AppsV1Api()
        self.v1_networking = client.NetworkingV1Api()
        self.custom_objects = client.CustomObjectsApi()

        logger.info("K8sClient initialized successfully")

    def create_namespace(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Namespace 생성

        Args:
            name: 생성할 namespace 이름
            labels: 네임스페이스 라벨 (선택사항)

        Returns:
            생성된 namespace 이름

        Raises:
            K8sClientError: namespace 생성 실패 시
        """
        namespace_manifest = client.V1Namespace(
            metadata=client.V1ObjectMeta(name=name, labels=labels or {})
        )

        try:
            # 네임스페이스가 이미 존재하는지 확인
            try:
                self.v1_core.read_namespace(name=name)
                logger.info(f"Namespace {name} already exists")
                return name
            except ApiException as e:
                if e.status != 404:
                    raise

            # 네임스페이스 생성
            self.v1_core.create_namespace(body=namespace_manifest)
            logger.info(f"✅ Namespace {name} created successfully")
            return name

        except ApiException as e:
            error_msg = f"Failed to create namespace {name}: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def create_knative_service(self, namespace: str, manifest: Dict) -> str:
        """
        KNative Service 생성

        Args:
            namespace: 배포할 네임스페이스
            manifest: KNative Service 매니페스트

        Returns:
            생성된 KNative Service 이름

        Raises:
            K8sClientError: 생성 실패 시
        """
        try:
            response = self.custom_objects.create_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1",
                namespace=namespace,
                plural="services",
                body=manifest,
            )

            service_name = response["metadata"]["name"]
            logger.info(
                f"✅ KNative Service {service_name} created successfully "
                f"(namespace: {namespace})"
            )
            return service_name

        except ApiException as e:
            error_msg = f"Failed to create KNative Service: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def create_ingress(self, namespace: str, manifest: client.V1Ingress) -> str:
        """
        Ingress 리소스 생성

        Args:
            namespace: Ingress가 생성될 네임스페이스
            manifest: Ingress 매니페스트

        Returns:
            생성된 Ingress 이름

        Raises:
            K8sClientError: Ingress 생성 실패 시
        """
        try:
            response = self.v1_networking.create_namespaced_ingress(
                namespace=namespace, body=manifest
            )

            ingress_name = response.metadata.name
            logger.info(f"✅ Ingress {ingress_name} created successfully")
            return ingress_name

        except ApiException as e:
            error_msg = f"Failed to create Ingress: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_namespace(self, name: str) -> bool:
        """
        Namespace 삭제 (관련된 모든 리소스 함께 삭제됨)

        Args:
            name: 삭제할 네임스페이스 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.v1_core.delete_namespace(name=name)
            logger.info(f"✅ Namespace {name} deleted successfully")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Namespace {name} already deleted or does not exist")
                return True
            error_msg = f"Failed to delete namespace {name}: {e.reason}"
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
            logger.info(f"✅ KNative Service {service_name} deleted successfully")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"KNative Service {service_name} already deleted or does not exist"
                )
                return True
            error_msg = f"Failed to delete KNative Service {service_name}: {e.reason}"
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
            logger.info(f"✅ Ingress {ingress_name} deleted successfully")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"Ingress {ingress_name} already deleted or does not exist"
                )
                return True
            error_msg = f"Failed to delete Ingress {ingress_name}: {e.reason}"
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
            logger.error(f"Failed to get namespace {namespace_name} status: {e.reason}")
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
            logger.error(
                f"Failed to get KNative Service {service_name} status: {e.reason}"
            )
            return None

    def create_cluster_domain_claim(self, domain: str, namespace: str) -> str:
        """
        ClusterDomainClaim 생성

        Args:
            domain: 클레임할 도메인 (예: workspace-alias.runna.haifu.cloud)
            namespace: 도메인을 사용할 네임스페이스

        Returns:
            생성된 ClusterDomainClaim 이름

        Raises:
            K8sClientError: 생성 실패 시
        """

        manifest = {
            "apiVersion": "networking.internal.knative.dev/v1alpha1",
            "kind": "ClusterDomainClaim",
            "metadata": {"name": domain},
            "spec": {"namespace": namespace},
        }

        try:
            self.custom_objects.create_cluster_custom_object(
                group="networking.internal.knative.dev",
                version="v1alpha1",
                plural="clusterdomainclaims",
                body=manifest,
            )

            logger.info(f"✅ ClusterDomainClaim {domain} created successfully")
            return domain

        except ApiException as e:
            if e.status == 409:
                logger.info(f"ClusterDomainClaim {domain} already exists")
                return domain
            error_msg = f"Failed to create ClusterDomainClaim: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_cluster_domain_claim(self, claim_name: str) -> bool:
        """
        ClusterDomainClaim 삭제

        Args:
            claim_name: 삭제할 클레임 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.custom_objects.delete_cluster_custom_object(
                group="networking.internal.knative.dev",
                version="v1alpha1",
                plural="clusterdomainclaims",
                name=claim_name,
            )
            logger.info(f"✅ ClusterDomainClaim {claim_name} deleted successfully")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"ClusterDomainClaim {claim_name} already deleted or does not exist"
                )
                return True
            error_msg = f"Failed to delete ClusterDomainClaim {claim_name}: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def create_domain_mapping(
        self, namespace: str, domain: str, service_name: str
    ) -> str:
        """
        DomainMapping 생성 (KNative Service와 도메인 연결)

        Args:
            namespace: DomainMapping이 생성될 네임스페이스
            domain: 매핑할 도메인
            service_name: 연결할 KNative Service 이름

        Returns:
            생성된 DomainMapping 이름

        Raises:
            K8sClientError: 생성 실패 시
        """

        manifest = {
            "apiVersion": "serving.knative.dev/v1alpha1",
            "kind": "DomainMapping",
            "metadata": {"name": domain, "namespace": namespace},
            "spec": {
                "ref": {
                    "name": service_name,
                    "kind": "Service",
                    "apiVersion": "serving.knative.dev/v1",
                }
            },
        }

        try:
            self.custom_objects.create_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="domainmappings",
                body=manifest,
            )

            logger.info(f"✅ DomainMapping {domain} created successfully")
            return domain

        except ApiException as e:
            if e.status == 409:
                logger.info(f"DomainMapping {domain} already exists")
                return domain
            error_msg = f"Failed to create DomainMapping: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_domain_mapping(self, namespace: str, mapping_name: str) -> bool:
        """
        DomainMapping 삭제

        Args:
            namespace: DomainMapping이 위치한 네임스페이스
            mapping_name: 삭제할 DomainMapping 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.custom_objects.delete_namespaced_custom_object(
                group="serving.knative.dev",
                version="v1alpha1",
                namespace=namespace,
                plural="domainmappings",
                name=mapping_name,
            )
            logger.info(f"✅ DomainMapping {mapping_name} deleted successfully")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"DomainMapping {mapping_name} already deleted or does not exist"
                )
                return True
            error_msg = f"Failed to delete DomainMapping {mapping_name}: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def create_http_route(
        self,
        namespace: str,
        hostname: str,
        path: str,
        service_name: str,
        gateway_name: str = "3scale-kourier-gateway",
    ) -> str:
        """
        Gateway API HTTPRoute 생성

        Args:
            namespace: HTTPRoute가 생성될 네임스페이스
            hostname: 라우팅할 호스트명 (예: workspace-alias.runna.haifu.cloud)
            path: 라우팅할 경로 (예: /my-function)
            service_name: 백엔드 KNative Service 이름
            gateway_name: Gateway 이름

        Returns:
            생성된 HTTPRoute 이름

        Raises:
            K8sClientError: 생성 실패 시
        """
        route_name = f"{service_name}-route"

        manifest = {
            "apiVersion": "gateway.networking.k8s.io/v1",
            "kind": "HTTPRoute",
            "metadata": {"name": route_name, "namespace": namespace},
            "spec": {
                "parentRefs": [{"name": gateway_name}],
                "hostnames": [hostname],
                "rules": [
                    {
                        "matches": [{"path": {"type": "PathPrefix", "value": path}}],
                        "backendRefs": [
                            {
                                "name": service_name,
                                "port": 80,
                                "kind": "Service",
                                "group": "serving.knative.dev",
                                "weight": 100,
                            }
                        ],
                    }
                ],
            },
        }

        try:
            self.custom_objects.create_namespaced_custom_object(
                group="gateway.networking.k8s.io",
                version="v1",
                namespace=namespace,
                plural="httproutes",
                body=manifest,
            )

            logger.info(f"✅ HTTPRoute {route_name} created successfully")
            return route_name

        except ApiException as e:
            if e.status == 409:
                logger.info(f"HTTPRoute {route_name} already exists")
                return route_name
            error_msg = f"Failed to create HTTPRoute: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)

    def delete_http_route(self, namespace: str, route_name: str) -> bool:
        """
        HTTPRoute 삭제

        Args:
            namespace: HTTPRoute가 위치한 네임스페이스
            route_name: 삭제할 HTTPRoute 이름

        Returns:
            삭제 성공 여부
        """
        try:
            self.custom_objects.delete_namespaced_custom_object(
                group="gateway.networking.k8s.io",
                version="v1",
                namespace=namespace,
                plural="httproutes",
                name=route_name,
            )
            logger.info(f"✅ HTTPRoute {route_name} deleted successfully")
            return True
        except ApiException as e:
            if e.status == 404:
                logger.warning(
                    f"HTTPRoute {route_name} already deleted or does not exist"
                )
                return True
            error_msg = f"Failed to delete HTTPRoute {route_name}: {e.reason}"
            logger.error(error_msg)
            raise K8sClientError(error_msg)
