import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from app.core.mock_namespace_manager import MockNamespaceManager
from app.core.namespace_manager import NamespaceManager
from app.core.sanitize import (
    sanitize_function_endpoint,
    validate_custom_endpoint,
)
from app.core.static_analysis import analyzer
from app.models.function import Function
from app.models.job import Job, JobStatus
from app.models.workspace import Workspace
from app.schemas.function import FunctionCreate, FunctionUpdate
from app.services.k8s_service import K8sService, K8sServiceError

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
                Function.workspace_id == workspace_id, Function.endpoint == endpoint
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
            if self.get_function_by_workspace_and_endpoint(
                function_data.workspace_id, endpoint
            ):
                raise ValueError(
                    f"Endpoint '{endpoint}' already exists in this workspace"
                )
        else:
            # 자동 생성 (workspace 내 중복 시 suffix 자동 추가)
            endpoint = sanitize_function_endpoint(
                function_data.name,
                workspace_id=function_data.workspace_id,
                db=self.db,
                max_attempts=10,
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

        # Namespace는 이제 workspace 생성 시에 미리 생성됨
        # Function은 workspace의 기존 namespace를 사용
        
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
                raise ValueError(
                    f"Endpoint '{new_endpoint}' already exists in this workspace"
                )
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

        # K8s 리소스 정리 (namespace는 유지, function 관련 리소스만 삭제)
        try:
            if workspace:
                self.k8s_service.cleanup_function_resources(db_function, workspace)
                logger.info(f"Cleaned up K8s resources for function {function_id}")
        except K8sServiceError as e:
            # K8s 정리 실패는 로그만 남기고 계속 진행
            logger.warning(f"Failed to cleanup K8s resources for function {function_id}: {e}")

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
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        함수를 Kubernetes에 배포

        Args:
            function_id: 배포할 함수 ID
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
            env_vars=env_vars,
        )

    def deploy(
        self,
        function_id: UUID,
        env_vars: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Function 배포 전체 워크플로우 실행
        
        1. Function 조회
        2. 유효성 검증 (코드, Runtime, 정적 분석)
        3. 상태 업데이트 (DEPLOYING)
        4. K8s 배포 실행
        5. 결과에 따른 상태 업데이트 (DEPLOYED/FAILED)
        
        Args:
            function_id: 배포할 함수 ID
            env_vars: 추가 환경변수 (선택사항)
            
        Returns:
            배포 결과 정보 {"status": "SUCCESS", "knative_url": "...", ...}
            
        Raises:
            ValueError: Function 없음, 코드 비어있음, Runtime 미지원, 정적 분석 실패
            K8sServiceError: K8s 배포 실패
        """
        from datetime import datetime
        from app.models.function import DeploymentStatus, Runtime
        
        # 1. Function 조회
        function = self.get_function(function_id)
        if not function:
            raise ValueError(f"Function with id {function_id} not found")
        
        # 2. 코드 존재 확인
        if not function.code or not function.code.strip():
            raise ValueError("Function code is empty. Cannot deploy without code.")
        
        # 3. Runtime 유효성 확인
        if function.runtime not in [Runtime.PYTHON, Runtime.NODEJS]:
            raise ValueError(f"Unsupported runtime: {function.runtime}. Only PYTHON and NODEJS are supported.")
        
        # 4. 정적 분석 (보안 검증)
        analysis_result = self._analyze_code(function.code, function.runtime.value)
        if not analysis_result["is_safe"]:
            raise ValueError(f"Code validation failed: {', '.join(analysis_result['violations'])}")
        
        # 5. 상태 업데이트: DEPLOYING
        function.deployment_status = DeploymentStatus.DEPLOYING
        function.deployment_error = None
        self.db.commit()
        
        try:
            # 6. K8s 배포 실행
            deploy_result = self.deploy_function_to_k8s(
                function_id=function_id,
                env_vars=env_vars,
            )
            
            # 7. 성공 처리
            function.deployment_status = DeploymentStatus.DEPLOYED
            function.knative_url = deploy_result["function_url"]
            function.last_deployed_at = datetime.utcnow()
            function.deployment_error = None
            self.db.commit()
            
            return {
                "status": "SUCCESS",
                "knative_url": function.knative_url,
                "message": "Deployment successful"
            }
            
        except Exception as e:
            # 8. 실패 처리
            self.db.rollback()
            function.deployment_status = DeploymentStatus.FAILED
            function.deployment_error = str(e)
            self.db.commit()
            raise

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
