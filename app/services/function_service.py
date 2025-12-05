import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.config import settings
from app.core.sanitize import (
    sanitize_function_endpoint,
    validate_custom_endpoint,
    SanitizationError,
)
from app.core.static_analysis import analyzer
from app.models.function import Function
from app.models.job import Job, JobStatus
from app.models.workspace import Workspace
from app.schemas.function import FunctionCreate, FunctionUpdate
from app.services.k8s_service import K8sService, K8sServiceError
from app.core.namespace_manager import NamespaceManager
from app.core.mock_namespace_manager import MockNamespaceManager

logger = logging.getLogger(__name__)


class FunctionService:
    def __init__(self, db: Session, namespace_manager=None):
        self.db = db

        # NamespaceManager 초기화 (fallback 메커니즘 포함)
        if namespace_manager is None:
            try:
                self.namespace_manager = NamespaceManager()
                logger.info("FunctionService initialized with real NamespaceManager")
            except Exception as e:
                logger.warning(
                    f"Failed to initialize NamespaceManager, using Mock: {e}"
                )
                self.namespace_manager = MockNamespaceManager()
        else:
            self.namespace_manager = namespace_manager

        self.k8s_service = K8sService(db)

    def get_function_by_endpoint(self, endpoint: str) -> Optional[Function]:
        """endpoint로 Function 조회 (전역 검색 - 하위 호환성용)"""
        return self.db.query(Function).filter(Function.endpoint == endpoint).first()

    def get_function_by_workspace_and_endpoint(
        self, workspace_id, endpoint: str
    ) -> Optional[Function]:
        """Workspace 내에서 endpoint로 Function 조회"""
        return (
            self.db.query(Function)
            .filter(
                Function.workspace_id == workspace_id,
                Function.endpoint == endpoint
            )
            .first()
        )

    def create_function(self, function_data: FunctionCreate) -> Function:
        # 1. 코드 분석
        analysis_result = self._analyze_code(
            function_data.code, function_data.runtime.value
        )

        if not analysis_result["is_safe"]:
            raise ValueError(
                f"Code analysis failed: {', '.join(analysis_result['violations'])}"
            )

        # 2. endpoint 생성 또는 검증
        if function_data.endpoint and function_data.endpoint.strip():
            # 사용자가 custom endpoint 제공 (빈 문자열 제외)
            endpoint = validate_custom_endpoint(function_data.endpoint)
            # Workspace 내 중복 확인
            if self.get_function_by_workspace_and_endpoint(function_data.workspace_id, endpoint):
                raise ValueError(f"Endpoint '{endpoint}' already exists in this workspace")
        else:
            # 자동 생성 (workspace 내 중복 시 suffix 자동 추가)
            endpoint = sanitize_function_endpoint(
                function_data.name,
                workspace_id=function_data.workspace_id,
                db=self.db,
                max_attempts=10
            )

        # 3. DB에 Function 생성
        function_dict = function_data.model_dump()
        function_dict["endpoint"] = endpoint  # endpoint 추가
        db_function = Function(**function_dict)
        self.db.add(db_function)
        self.db.commit()
        self.db.refresh(db_function)

        # 4. Workspace 정보 조회
        workspace = (
            self.db.query(Workspace)
            .filter(Workspace.id == db_function.workspace_id)
            .first()
        )

        if not workspace:
            # Function 삭제 후 에러 발생
            self.db.delete(db_function)
            self.db.commit()
            raise ValueError("Workspace not found")

        # 5. Namespace 생성
        try:
            namespace = self.namespace_manager.create_function_namespace(
                workspace.name, str(db_function.id)  # UUID를 문자열로 변환
            )
            logger.info(f"Created namespace {namespace} for function {db_function.id}")
        except Exception as e:
            # Namespace 생성 실패 시 Function 삭제 (rollback)
            logger.error(
                f"Failed to create namespace for function {db_function.id}: {e}"
            )
            self.db.delete(db_function)
            self.db.commit()
            raise ValueError(f"Failed to create namespace: {e}")

        return db_function

    def get_function(self, function_id: UUID) -> Optional[Function]:
        return self.db.query(Function).filter(Function.id == function_id).first()

    def get_function_by_name(self, name: str) -> Optional[Function]:
        return self.db.query(Function).filter(Function.name == name).first()

    def list_functions(self, skip: int = 0, limit: int = 100) -> List[Function]:
        return self.db.query(Function).offset(skip).limit(limit).all()

    def update_function(
        self, function_id: UUID, function_update: FunctionUpdate
    ) -> Optional[Function]:
        db_function = self.get_function(function_id)
        if not db_function:
            return None

        update_data = function_update.model_dump(exclude_unset=True)

        # 코드 검증
        if "code" in update_data:
            runtime = update_data.get("runtime", db_function.runtime)
            analysis_result = self._analyze_code(
                update_data["code"],
                runtime.value if hasattr(runtime, "value") else runtime,
            )

            if not analysis_result["is_safe"]:
                raise ValueError(
                    f"Code analysis failed: {', '.join(analysis_result['violations'])}"
                )

        # endpoint 검증 및 변경
        if "endpoint" in update_data:
            new_endpoint = validate_custom_endpoint(update_data["endpoint"])
            # Workspace 내 중복 확인 (자신 제외)
            existing = self.get_function_by_workspace_and_endpoint(
                db_function.workspace_id, new_endpoint
            )
            if existing and existing.id != db_function.id:
                raise ValueError(f"Endpoint '{new_endpoint}' already exists in this workspace")
            update_data["endpoint"] = new_endpoint

        for field, value in update_data.items():
            setattr(db_function, field, value)

        self.db.commit()
        self.db.refresh(db_function)
        return db_function

    def delete_function(self, function_id: UUID) -> bool:
        db_function = self.get_function(function_id)
        if not db_function:
            return False

        # Workspace 정보 조회
        workspace = (
            self.db.query(Workspace)
            .filter(Workspace.id == db_function.workspace_id)
            .first()
        )

        # Namespace 삭제
        if workspace:
            try:
                self.namespace_manager.delete_function_namespace(
                    workspace.name, str(function_id)  # UUID를 문자열로 변환
                )
                logger.info(f"Deleted namespace for function {function_id}")
            except Exception as e:
                logger.error(
                    f"Failed to delete namespace for function {function_id}: {e}"
                )
                # namespace 삭제 실패해도 DB는 삭제 진행

        try:
            # K8s 리소스 정리 (실패해도 DB 정리는 계속 진행)
            if workspace:
                self.k8s_service.cleanup_function_resources(db_function, workspace)
        except K8sServiceError as e:
            # K8s 정리 실패는 로그만 남기고 계속 진행
            print(f"Failed to cleanup K8s resources: {e}")

        # Delete the function and related jobs
        self.db.query(Job).filter(Job.function_id == function_id).delete()
        self.db.delete(db_function)
        self.db.commit()
        return True

    def get_function_metrics(self, function_id: UUID) -> Optional[Dict[str, Any]]:
        function = self.get_function(function_id)
        if not function:
            return None

        # Get metrics directly from Job table
        total_jobs = self.db.query(Job).filter(Job.function_id == function_id).count()

        successful_jobs = (
            self.db.query(Job)
            .filter(Job.function_id == function_id, Job.status == JobStatus.SUCCESS)
            .count()
        )

        failed_jobs = (
            self.db.query(Job)
            .filter(Job.function_id == function_id, Job.status == JobStatus.FAILED)
            .count()
        )

        success_rate = (successful_jobs / total_jobs * 100) if total_jobs > 0 else 0

        return {
            "invocations": {
                "total": total_jobs,
                "successful": successful_jobs,
                "failed": failed_jobs,
            },
            "success_rate": round(success_rate, 2),
            "avg_execution_time": "120ms",  # TODO: Calculate from actual data
            "cpu_usage": "70%",  # TODO: Get from monitoring system
            "memory_usage": "256MB",  # TODO: Get from monitoring system
        }

    def deploy_function_to_k8s(
        self,
        function_id: UUID,
        custom_path: str,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        함수를 Kubernetes에 배포

        Args:
            function_id: 배포할 함수 ID
            custom_path: 사용자 정의 경로
            env_vars: 추가 환경변수 (선택사항)

        Returns:
            배포 결과 정보

        Raises:
            ValueError: 함수 또는 워크스페이스를 찾을 수 없는 경우
            K8sServiceError: K8s 배포 실패 시
        """
        function = self.get_function(function_id)
        if not function:
            raise ValueError(f"Function with id {function_id} not found")

        workspace = (
            self.db.query(Workspace)
            .filter(Workspace.id == function.workspace_id)
            .first()
        )
        if not workspace:
            raise ValueError(f"Workspace for function {function_id} not found")

        return self.k8s_service.deploy_function(
            function=function,
            workspace=workspace,
            custom_path=custom_path,
            env_vars=env_vars,
        )

    def get_function_deployment_status(self, function_id: UUID) -> Optional[Dict]:
        """
        함수 배포 상태 확인

        Args:
            function_id: 상태를 확인할 함수 ID

        Returns:
            배포 상태 정보 또는 None
        """
        function = self.get_function(function_id)
        if not function:
            return None

        workspace = (
            self.db.query(Workspace)
            .filter(Workspace.id == function.workspace_id)
            .first()
        )
        if not workspace:
            return None

        return self.k8s_service.get_function_status(function, workspace)

    def _analyze_code(self, code: str, runtime: str) -> dict:
        if runtime == "PYTHON":
            return analyzer.analyze_python_code(code)
        elif runtime == "NODEJS":
            return analyzer.analyze_nodejs_code(code)
        else:
            return {"is_safe": False, "violations": ["Unsupported runtime"]}
