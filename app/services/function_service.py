from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.static_analysis import analyzer
from app.models.function import Function
from app.models.job import Job, JobStatus
from app.models.workspace import Workspace
from app.schemas.function import FunctionCreate, FunctionUpdate
from app.services.k8s_service import K8sService, K8sServiceError


class FunctionService:
    def __init__(self, db: Session):
        self.db = db
        self.k8s_service = K8sService(db)

    def create_function(self, function_data: FunctionCreate) -> Function:
        analysis_result = self._analyze_code(
            function_data.code, function_data.runtime.value
        )

        if not analysis_result["is_safe"]:
            raise ValueError(
                f"Code analysis failed: {', '.join(analysis_result['violations'])}"
            )

        db_function = Function(**function_data.model_dump())
        self.db.add(db_function)
        self.db.commit()
        self.db.refresh(db_function)
        return db_function

    def get_function(self, function_id: int) -> Optional[Function]:
        return self.db.query(Function).filter(Function.id == function_id).first()

    def get_function_by_name(self, name: str) -> Optional[Function]:
        return self.db.query(Function).filter(Function.name == name).first()

    def list_functions(self, skip: int = 0, limit: int = 100) -> List[Function]:
        return self.db.query(Function).offset(skip).limit(limit).all()

    def update_function(
        self, function_id: int, function_update: FunctionUpdate
    ) -> Optional[Function]:
        db_function = self.get_function(function_id)
        if not db_function:
            return None

        update_data = function_update.model_dump(exclude_unset=True)

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

        for field, value in update_data.items():
            setattr(db_function, field, value)

        self.db.commit()
        self.db.refresh(db_function)
        return db_function

    def delete_function(self, function_id: int) -> bool:
        db_function = self.get_function(function_id)
        if not db_function:
            return False

        # Get workspace for K8s cleanup
        workspace = (
            self.db.query(Workspace)
            .filter(Workspace.id == db_function.workspace_id)
            .first()
        )

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

    def get_function_metrics(self, function_id: int) -> Optional[Dict[str, Any]]:
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
        function_id: int,
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

    def get_function_deployment_status(self, function_id: int) -> Optional[Dict]:
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
        if runtime == "python":
            return analyzer.analyze_python_code(code)
        elif runtime == "nodejs":
            return analyzer.analyze_nodejs_code(code)
        else:
            return {"is_safe": False, "violations": ["Unsupported runtime"]}
