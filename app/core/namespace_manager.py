import logging
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from app.config import settings

logger = logging.getLogger(__name__)


class NamespaceManagerError(Exception):
    """NamespaceManager 관련 예외"""
    pass


class NamespaceManager:
    """
    Kubernetes Namespace 생성 및 관리

    Function마다 독립된 namespace를 생성하여:
    - 메트릭 수집 격리
    - 보안 격리
    - 리소스 쿼터 적용
    """

    def __init__(self):
        """Kubernetes 클라이언트 초기화"""
        try:
            if settings.kubernetes_in_cluster:
                config.load_incluster_config()  # Pod 내부
            else:
                config.load_kube_config(settings.kubernetes_config_path)  # 로컬
        except Exception as e:
            logger.error(f"Failed to load Kubernetes config: {e}")
            raise NamespaceManagerError(f"Failed to initialize Kubernetes client: {e}") from e

        self.core_v1 = client.CoreV1Api()
        self.networking_v1 = client.NetworkingV1Api()

    def create_function_namespace(
        self,
        workspace_name: str,
        function_id: str
    ) -> str:
        """
        Function을 위한 namespace 생성

        Args:
            workspace_name: Workspace 이름 (최대 20자, API/Model Layer에서 이미 검증됨)
            function_id: Function UUID (36자, 시스템 생성으로 안전함)

        Returns:
            생성된 namespace 이름

        Raises:
            ValueError: namespace 이름이 63자 초과
            ApiException: Kubernetes API 호출 실패
        """
        # Namespace 이름 생성
        # 형식: {workspace_name}-{function_uuid}
        # 최대 길이: 20 + 1 + 36 = 57자 (63자 제한 안전)
        namespace = f"{workspace_name}-{function_id}"

        # 길이 검증만 수행 (Kubernetes 제약)
        if len(namespace) > 63:
            logger.error(f"✗ Namespace name exceeds 63 characters: {namespace} ({len(namespace)})")
            raise ValueError(
                f"Namespace name exceeds 63 characters: {namespace} ({len(namespace)})"
            )

        # Namespace 생성
        namespace_body = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace,
                labels={
                    "app": "runna",
                    "workspace": workspace_name,
                    "function-id": function_id,
                    "managed-by": "runna-backend"
                }
            )
        )

        try:
            self.core_v1.create_namespace(namespace_body)
            logger.info(f"✓ Created namespace: {namespace}")
        except ApiException as e:
            if e.status == 409:  # Already exists
                logger.info(f"✓ Namespace already exists: {namespace}")
            else:
                logger.error(f"✗ Failed to create namespace {namespace}: {e}")
                raise

        # 리소스 제한 적용
        # NOTE: 클러스터 측 Policy Controller가 자동으로 적용하므로 주석 처리
        # 필요 시 아래 주석을 해제하여 수동 적용 가능
        # try:
        #     self._apply_resource_quota(namespace)
        #     self._apply_limit_range(namespace)
        #     self._apply_network_policy(namespace)
        #     logger.info(f"✓ Applied policies to namespace: {namespace}")
        # except Exception as e:
        #     logger.error(f"✗ Failed to apply policies: {e}")
        #     # Namespace는 생성되었으므로 계속 진행

        logger.info(f"✓ Namespace created. Resource policies will be auto-applied by cluster.")
        return namespace

    def _apply_resource_quota(self, namespace: str):
        """
        Namespace에 ResourceQuota 적용

        전체 namespace에서 사용 가능한 리소스 총량 제한
        """
        quota = client.V1ResourceQuota(
            metadata=client.V1ObjectMeta(name="runna-quota"),
            spec=client.V1ResourceQuotaSpec(
                hard={
                    "requests.cpu": settings.namespace_cpu_limit,
                    "requests.memory": settings.namespace_memory_limit,
                    "limits.cpu": settings.namespace_cpu_limit,
                    "limits.memory": settings.namespace_memory_limit,
                    "pods": str(settings.namespace_pod_limit)
                }
            )
        )

        try:
            self.core_v1.create_namespaced_resource_quota(namespace, quota)
        except ApiException as e:
            if e.status == 409:
                logger.info(f"ResourceQuota already exists in {namespace}")
            else:
                raise

    def _apply_limit_range(self, namespace: str):
        """
        Namespace에 LimitRange 적용

        개별 Pod/Container의 기본 리소스 제한
        """
        limit_range = client.V1LimitRange(
            metadata=client.V1ObjectMeta(name="runna-limits"),
            spec=client.V1LimitRangeSpec(
                limits=[
                    client.V1LimitRangeItem(
                        type="Container",
                        default={
                            "cpu": "500m",
                            "memory": "512Mi"
                        },
                        default_request={
                            "cpu": "100m",
                            "memory": "128Mi"
                        },
                        max={
                            "cpu": "1000m",
                            "memory": "1Gi"
                        }
                    )
                ]
            )
        )

        try:
            self.core_v1.create_namespaced_limit_range(namespace, limit_range)
        except ApiException as e:
            if e.status == 409:
                logger.info(f"LimitRange already exists in {namespace}")
            else:
                raise

    def _apply_network_policy(self, namespace: str):
        """
        Namespace에 NetworkPolicy 적용

        Namespace 간 네트워크 격리 (동일 Function의 Pod끼리만 통신)
        """
        network_policy = client.V1NetworkPolicy(
            metadata=client.V1ObjectMeta(name="runna-isolation"),
            spec=client.V1NetworkPolicySpec(
                pod_selector=client.V1LabelSelector(),  # 모든 Pod에 적용
                policy_types=["Ingress", "Egress"],
                ingress=[
                    # 동일 namespace 내에서만 ingress 허용
                    client.V1NetworkPolicyIngressRule(
                        from_=[
                            client.V1NetworkPolicyPeer(
                                namespace_selector=client.V1LabelSelector(
                                    match_labels={"name": namespace}
                                )
                            )
                        ]
                    )
                ],
                egress=[
                    # 모든 egress 허용 (외부 API 호출 등)
                    client.V1NetworkPolicyEgressRule(
                        to=[client.V1NetworkPolicyPeer()]
                    )
                ]
            )
        )

        try:
            self.networking_v1.create_namespaced_network_policy(namespace, network_policy)
        except ApiException as e:
            if e.status == 409:
                logger.info(f"NetworkPolicy already exists in {namespace}")
            else:
                raise

    def delete_function_namespace(
        self,
        workspace_name: str,
        function_id: str
    ):
        """
        Function namespace 삭제

        Args:
            workspace_name: Workspace 이름 (이미 검증됨)
            function_id: Function UUID (이미 검증됨)
        """
        namespace = f"{workspace_name}-{function_id}"

        try:
            self.core_v1.delete_namespace(name=namespace)
            logger.info(f"✓ Deleted namespace: {namespace}")
        except ApiException as e:
            if e.status == 404:
                logger.warning(f"Namespace not found: {namespace}")
            else:
                logger.error(f"✗ Failed to delete namespace: {e}")
                raise

    def namespace_exists(
        self,
        workspace_name: str,
        function_id: str
    ) -> bool:
        """
        Namespace 존재 여부 확인

        Args:
            workspace_name: Workspace 이름 (이미 검증됨)
            function_id: Function UUID (이미 검증됨)

        Returns:
            존재 여부
        """
        namespace = f"{workspace_name}-{function_id}"

        try:
            self.core_v1.read_namespace(name=namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                return False
            raise
