import logging

logger = logging.getLogger(__name__)


class MockNamespaceManager:
    """
    Kubernetes 없이 테스트하기 위한 Mock NamespaceManager

    실제 K8s API를 호출하지 않고 로그만 출력합니다.
    개발 환경 및 CI/CD에서 Kubernetes 없이 전체 플로우를 테스트할 수 있습니다.
    """

    def __init__(self):
        logger.info("MockNamespaceManager initialized (Kubernetes disabled)")
        self._created_namespaces = set()  # 생성된 namespace 추적용

    def create_function_namespace(
        self,
        workspace_name: str,
        function_id: str
    ) -> str:
        """
        Mock: Namespace 생성 시뮬레이션

        Args:
            workspace_name: Workspace 이름 (최대 20자, 검증됨)
            function_id: Function UUID (36자)

        Returns:
            생성된 namespace 이름

        Raises:
            ValueError: namespace 이름이 63자 초과
        """
        # 1. Namespace 이름 생성
        # 형식: {workspace_name}-{function_uuid}
        namespace = f"{workspace_name}-{function_id}"

        # 2. 길이 검증 (실제 NamespaceManager와 동일)
        if len(namespace) > 63:
            raise ValueError(
                f"Namespace name exceeds 63 characters: {namespace} ({len(namespace)})"
            )

        # 3. Mock 로그 출력
        logger.info(f"[MOCK] Created namespace: {namespace}")
        logger.info(f"[MOCK]   Labels: app=runna, workspace={workspace_name}, function-id={function_id}")
        logger.info(f"[MOCK] Applied ResourceQuota to {namespace}")
        logger.info(f"[MOCK]   CPU: 2000m, Memory: 4Gi, Pods: 10")
        logger.info(f"[MOCK] Applied LimitRange to {namespace}")
        logger.info(f"[MOCK]   Default CPU: 500m, Default Memory: 512Mi")
        logger.info(f"[MOCK] Applied NetworkPolicy to {namespace}")
        logger.info(f"[MOCK]   Ingress: same namespace only, Egress: all allowed")

        # 4. 내부 상태 업데이트
        self._created_namespaces.add(namespace)

        return namespace

    def delete_function_namespace(
        self,
        workspace_name: str,
        function_id: str
    ):
        """
        Mock: Namespace 삭제 시뮬레이션

        Args:
            workspace_name: Workspace 이름
            function_id: Function UUID
        """
        namespace = f"{workspace_name}-{function_id}"

        logger.info(f"[MOCK] Deleted namespace: {namespace}")

        # 내부 상태 업데이트
        self._created_namespaces.discard(namespace)

    def namespace_exists(
        self,
        workspace_name: str,
        function_id: str
    ) -> bool:
        """
        Mock: Namespace 존재 여부 확인

        Args:
            workspace_name: Workspace 이름
            function_id: Function UUID

        Returns:
            존재 여부 (Mock 내부 상태 기준)
        """
        namespace = f"{workspace_name}-{function_id}"
        exists = namespace in self._created_namespaces

        logger.info(f"[MOCK] Namespace {namespace} exists: {exists}")
        return exists

    def get_created_namespaces(self) -> set:
        """
        Mock 전용: 생성된 namespace 목록 반환 (테스트용)

        Returns:
            생성된 namespace 이름 set
        """
        return self._created_namespaces.copy()
