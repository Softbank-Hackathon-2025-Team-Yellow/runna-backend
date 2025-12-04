import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.core.static_analysis import analyzer
from app.models.function import Function
from app.models.job import Job, JobStatus
from app.models.workspace import Workspace
from app.schemas.function import FunctionCreate, FunctionUpdate

logger = logging.getLogger(__name__)

# Kubernetes 사용 여부에 따라 다른 Manager 임포트
if settings.kubernetes_in_cluster or settings.kubernetes_config_path:
    try:
        from app.core.namespace_manager import NamespaceManager
        logger.info("Using real NamespaceManager (Kubernetes enabled)")
    except Exception as e:
        logger.warning(f"Failed to load NamespaceManager, using Mock: {e}")
        from app.core.mock_namespace_manager import MockNamespaceManager as NamespaceManager
else:
    from app.core.mock_namespace_manager import MockNamespaceManager as NamespaceManager
    logger.info("Using MockNamespaceManager (Kubernetes disabled)")


class FunctionService:
    def __init__(self, db: Session, namespace_manager=None):
        self.db = db
        self.namespace_manager = namespace_manager or NamespaceManager()

    def create_function(self, function_data: FunctionCreate) -> Function:
        # 1. 코드 분석
        analysis_result = self._analyze_code(
            function_data.code, function_data.runtime.value
        )

        if not analysis_result["is_safe"]:
            raise ValueError(
                f"Code analysis failed: {', '.join(analysis_result['violations'])}"
            )

        # 2. DB에 Function 생성
        db_function = Function(**function_data.model_dump())
        self.db.add(db_function)
        self.db.commit()
        self.db.refresh(db_function)

        # 3. Workspace 정보 조회
        workspace = self.db.query(Workspace).filter(
            Workspace.id == db_function.workspace_id
        ).first()

        if not workspace:
            # Function 삭제 후 에러 발생
            self.db.delete(db_function)
            self.db.commit()
            raise ValueError("Workspace not found")

        # 4. Namespace 생성
        try:
            namespace = self.namespace_manager.create_function_namespace(
                workspace.name,
                str(db_function.id)  # UUID를 문자열로 변환
            )
            logger.info(f"Created namespace {namespace} for function {db_function.id}")
        except Exception as e:
            # Namespace 생성 실패 시 Function 삭제 (rollback)
            logger.error(f"Failed to create namespace for function {db_function.id}: {e}")
            self.db.delete(db_function)
            self.db.commit()
            raise ValueError(f"Failed to create namespace: {e}")

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

        # Workspace 정보 조회
        workspace = self.db.query(Workspace).filter(
            Workspace.id == db_function.workspace_id
        ).first()

        # Namespace 삭제
        if workspace:
            try:
                self.namespace_manager.delete_function_namespace(
                    workspace.name,
                    str(function_id)  # UUID를 문자열로 변환
                )
                logger.info(f"Deleted namespace for function {function_id}")
            except Exception as e:
                logger.error(f"Failed to delete namespace for function {function_id}: {e}")
                # namespace 삭제 실패해도 DB는 삭제 진행

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

    def _analyze_code(self, code: str, runtime: str) -> dict:
        if runtime == "python":
            return analyzer.analyze_python_code(code)
        elif runtime == "nodejs":
            return analyzer.analyze_nodejs_code(code)
        else:
            return {"is_safe": False, "violations": ["Unsupported runtime"]}
